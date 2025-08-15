from fastapi import Request

from app.services.reading_repository import ReadingRepository


def get_deck_loader(request: Request):
    return request.app.state.deck_loader


def get_reading_repo(request: Request) -> ReadingRepository:
    return request.app.state.reading_repo
