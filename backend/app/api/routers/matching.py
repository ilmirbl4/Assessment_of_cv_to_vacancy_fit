"""Справочники, подбор вакансий, страница вакансии и избранное."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import ContainerDep, Seeker
from app.api.routers.common import errors
from app.config import MAX_PAGE, PAGE_SIZE
from app.domain.models import MatchFilters as DomainFilters
from app.reference import EMPLOYMENT, EXPERIENCE, SCHEDULES, regions
from app.schemas.models import (
    REQUIREMENT_STATUS,
    Dictionaries,
    Empty,
    FavoriteItem,
    FavoriteRequest,
    MatchPage,
    MatchRunRequest,
    Option,
    Requirement,
    SourceField,
    VacancyDetail,
    card_out,
    date_str,
    favorite_vacancy_out,
    filters_out,
    iso,
)
from app.services.matching import MatchPageData

router = APIRouter()


def _page_out(data: MatchPageData, timezone: str) -> MatchPage:
    return MatchPage(
        run_id=data.run.id,
        created_at=iso(data.run.created_at, timezone),
        filters=filters_out(data.run.filters),
        total=len(data.run.results),
        page=data.page,
        page_size=PAGE_SIZE,
        total_pages=data.total_pages,
        items=[card_out(vacancy, percent) for vacancy, percent in data.items],
    )


@router.get(
    "/dictionaries",
    response_model=Dictionaries,
    summary="Справочники фильтров",
    description="Регионы, типы занятости, графики работы и требуемый опыт.",
)
async def dictionaries(response: Response) -> Dictionaries:
    """Справочники фильтров."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return Dictionaries(
        regions=[Option(code=o.code, name=o.name) for o in regions()],
        employment_types=[Option(code=o.code, name=o.name) for o in EMPLOYMENT],
        schedules=[Option(code=o.code, name=o.name) for o in SCHEDULES],
        experience=[Option(code=o.code, name=o.name) for o in EXPERIENCE],
    )


@router.post(
    "/matching/runs",
    status_code=201,
    response_model=MatchPage,
    summary="Запуск подбора",
    description="Подбирает до 100 вакансий под резюме и фильтры; возвращает первую страницу.",
    responses=errors(401, 403, 409, 422),
)
async def start_matching(body: MatchRunRequest, user: Seeker, container: ContainerDep) -> MatchPage:
    """Запуск подбора."""
    f = body.filters
    filters = DomainFilters(
        f.region_code, f.min_salary, f.only_with_salary, f.employment_type, f.schedule, f.experience
    )
    data = await container.matching.start(user, filters)
    return _page_out(data, container.settings.app_timezone)


@router.get(
    "/matching/runs/current",
    response_model=MatchPage,
    summary="Страница текущего подбора",
    description="Возвращает страницу результатов последнего подбора пользователя.",
    responses=errors(401, 403, 404, 422),
)
async def current_matching(
    user: Seeker, container: ContainerDep, page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1
) -> MatchPage:
    """Страница текущего подбора."""
    return _page_out(await container.matching.current(user, page), container.settings.app_timezone)


@router.get(
    "/vacancies/{vacancy_id:path}",
    response_model=VacancyDetail,
    summary="Страница вакансии",
    description="Вакансия со всеми полями источника и вердиктами по требованиям.",
    responses=errors(401, 403, 404),
)
async def vacancy_detail(vacancy_id: str, user: Seeker, container: ContainerDep) -> VacancyDetail:
    """Страница вакансии."""
    data = await container.matching.detail(user, vacancy_id)
    v = data.vacancy
    return VacancyDetail(
        id=v.id,
        title=v.title,
        salary_from=v.salary_from,
        salary_to=v.salary_to,
        employer_name=v.employer_name,
        published_at=date_str(v.published_at),
        match_percent=data.match_percent,
        region_name=v.region_name,
        source_url=v.source_url,
        is_active=v.is_active,
        is_favorite=data.is_favorite,
        source_fields=[SourceField(label=f.label, value=f.value) for f in v.source_fields],
        requirements=[
            Requirement(number=r.number, text=r.text, status=REQUIREMENT_STATUS[r.status], resume_quote=r.resume_quote)
            for r in data.verdicts
        ],
    )


@router.get(
    "/favorites",
    response_model=list[FavoriteItem],
    summary="Избранное",
    description="Избранные вакансии по убыванию даты добавления.",
    responses=errors(401, 403),
)
async def list_favorites(user: Seeker, container: ContainerDep) -> list[FavoriteItem]:
    """Список избранного."""
    tz = container.settings.app_timezone
    return [
        FavoriteItem(vacancy=favorite_vacancy_out(v), is_active=v.is_active, added_at=iso(fav.added_at, tz))
        for fav, v in await container.matching.favorites(user)
    ]


@router.post(
    "/favorites",
    status_code=201,
    response_model=Empty,
    summary="Добавить в избранное",
    description="Добавляет вакансию в избранное.",
    responses=errors(401, 403, 404, 409, 422),
)
async def add_favorite(body: FavoriteRequest, user: Seeker, container: ContainerDep) -> Empty:
    """Добавление в избранное."""
    await container.matching.add_favorite(user, body.vacancy_id)
    return Empty()


@router.delete(
    "/favorites/{vacancy_id}",
    status_code=204,
    response_class=Response,
    summary="Удалить из избранного",
    description="Удаляет вакансию из избранного; повторное удаление не считается ошибкой.",
    responses=errors(401, 403),
)
async def remove_favorite(vacancy_id: str, user: Seeker, container: ContainerDep) -> Response:
    """Удаление из избранного."""
    await container.matching.remove_favorite(user, vacancy_id)
    return Response(status_code=204)
