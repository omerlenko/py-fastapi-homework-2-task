from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas import MovieListResponseSchema, MovieDetailSchema
from schemas.movies import MovieCreateSchema, MovieUpdateSchema

router = APIRouter()
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_or_create_by_names(db: AsyncSession, model, names: list[str]):
    names = {name.lower(): name for name in names}
    result = await db.scalars(select(model).where(func.lower(model.name).in_(names.keys())))
    existing = {model_instance.name.lower(): model_instance for model_instance in result}
    objects = [existing.get(key) or model(name=original) for key, original in names.items()]

    return objects


async def get_movie_or_404(db: AsyncSession, movie_id: int):
    movie = await db.get(
        MovieModel,
        movie_id,
        options=[
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages)
        ]
    )
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return movie


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(db: DbDep, page: int = Query(default=1, ge=1), per_page: int = Query(default=10, ge=1, le=20)):
    offset = (page - 1) * per_page
    stmt = select(MovieModel).order_by(MovieModel.id.desc()).offset(offset).limit(per_page)
    result = await db.scalars(stmt)
    movies = list(result.all())
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    stmt_total = select(func.count(MovieModel.id))
    total_movies = await db.scalar(stmt_total)
    total_pages = max(1, ceil(total_movies / per_page))

    prev_page = f"/theater/movies/?page={page - 1}&per_page={per_page}"
    if page == 1:
        prev_page = None
    next_page = f"/theater/movies/?page={page + 1}&per_page={per_page}"
    if page == total_pages:
        next_page = None

    return {
        "movies": movies,
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": total_movies,
    }


@router.post("/movies/", response_model=MovieDetailSchema, status_code=201)
async def create_movie(db: DbDep, data: MovieCreateSchema):
    stmt = select(MovieModel).where(MovieModel.name == data.name, MovieModel.date == data.date)
    result = await db.scalars(stmt)
    existing_movie = result.one_or_none()
    if existing_movie is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{data.name}' and release date '{data.date}' already exists."
        )

    country_result = await db.scalars(select(CountryModel).where(CountryModel.code == data.country))
    country = country_result.one_or_none()
    if country is None:
        country = CountryModel(code=data.country)
        db.add(country)

    genres = await get_or_create_by_names(db=db, model=GenreModel, names=data.genres)
    actors = await get_or_create_by_names(db=db, model=ActorModel, names=data.actors)
    languages = await get_or_create_by_names(db=db, model=LanguageModel, names=data.languages)

    movie = MovieModel(
        **data.model_dump(exclude={"country", "genres", "actors", "languages"}),
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )
    db.add(movie)
    await db.commit()
    await db.refresh(movie, ["country", "genres", "actors", "languages"])

    return movie


@router.get("/movies/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie(db: DbDep, movie_id: int):
    return await get_movie_or_404(db=db, movie_id=movie_id)


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(db: DbDep, movie_id: int):
    movie = await get_movie_or_404(db=db, movie_id=movie_id)
    await db.delete(movie)
    await db.commit()


@router.patch("/movies/{movie_id}/", response_model=dict[str, str])
async def update_movie(db: DbDep, movie_id: int, data: MovieUpdateSchema):
    movie = await get_movie_or_404(db=db, movie_id=movie_id)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(movie, key, value)
    name = movie.name
    date = movie.date

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{name}' and release date '{date}' already exists."
        )
    return {"detail": "Movie updated successfully."}
