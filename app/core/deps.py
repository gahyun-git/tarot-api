from fastapi import Request


def get_deck_loader(request: Request):
    return request.app.state.deck_loader
