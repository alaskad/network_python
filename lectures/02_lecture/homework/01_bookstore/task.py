"""
01_bookstore — CRUD API для книжного магазина 📚

Спроектируйте REST API для управления каталогом книг.

Спецификация эндпоинтов (ничего не менять — тесты завязаны на них):

    GET    /books              — список книг (с опциональной фильтрацией)
    GET    /books/{id}         — одна книга по id
    POST   /books              — создать книгу
    PUT    /books/{id}         — полностью обновить книгу
    DELETE /books/{id}         — удалить книгу
    GET    /books/search       — поиск книг по названию или автору

    # Дополнительно — категории
    GET    /categories         — список категорий
    POST   /categories         — создать категорию

Требования к реализации:
    1. Используйте FastAPI + Pydantic
    2. Храните данные в памяти (глобальный список/словарь)
    3. Правильные HTTP-статусы:
        - 200 — успешный GET, PUT
        - 201 — успешный POST
        - 204 — успешный DELETE
        - 404 — ресурс не найден
        - 409 — конфликт (например, дубликат)
        - 422 — невалидные данные (Pydantic сам это делает)
    4. Валидация полей через Pydantic Field:
        - title:  не пустой, до 100 символов
        - author: не пустой, до 100 символов
        - year:   ≥ 0, до 2025
        - isbn:   строка 10 или 13 цифр (978-5-xxx...)
        - price:  > 0
        - category_id: опционально, ссылка на категорию
    5. Кастомная обработка ошибок:
        - BookNotFoundException → 404 c {"detail": "Book not found", "code": "NOT_FOUND"}
        - DuplicateIsbnException → 409 c {"detail": "...", "code": "DUPLICATE_ISBN"}
    6. Поиск /books/search?query=... — ищет по title и author (case-insensitive)
    7. Фильтрация GET /books?category_id=N&year=2024
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional

# ═══════════════════════════════════════════════════════════
# МОДЕЛИ
# ═══════════════════════════════════════════════════════════


class Category(BaseModel):
    """Доменная модель категории. Возвращается в ответах."""

    id: int
    name: str = Field(min_length=1, max_length=50)


class CategoryCreate(BaseModel):
    """Модель для создания категории (без id, лишние поля запрещены)."""

    name: str = Field(min_length=1, max_length=50)

    model_config = {"extra": "forbid"}


class Book(BaseModel):
    """Доменная модель книги. Возвращается в ответах GET/PUT."""

    id: int
    title: str = Field(min_length=1, max_length=100)
    author: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1900, le=2025)
    isbn: str
    price: float = Field(gt=0)
    category_id: Optional[int] = None


class BookCreate(BaseModel):
    """Модель для создания/обновления книги (без id — сервер сгенерирует)."""

    title: str = Field(min_length=1, max_length=100)
    author: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1900, le=2025)
    isbn: str
    price: float = Field(gt=0)
    category_id: Optional[int] = None


# ═══════════════════════════════════════════════════════════
# ИСКЛЮЧЕНИЯ
# ═══════════════════════════════════════════════════════════


class BookNotFoundException(HTTPException):
    """404 — книга не найдена."""
    def __init__(self):
        super().__init__(status_code=404, detail="Book not found")

class DuplicateIsbnException(HTTPException):
    """409 — ISBN уже существует."""
    def __init__(self, isbn: str):
        self.isbn = isbn
        super().__init__(status_code=409, detail=f"Book with ISBN {isbn} already exists")

# ═══════════════════════════════════════════════════════════
# ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════════════════════════

app = FastAPI(title="Bookstore API")
@app.exception_handler(BookNotFoundException)
def book_not_found_handler(request: Request, exc: BookNotFoundException):
    return JSONResponse(status_code=404, content={"detail": "Book not found", "code": "NOT_FOUND"},)

@app.exception_handler(DuplicateIsbnException)
def duplicate_isbn_handler(request: Request, exc: DuplicateIsbnException):
    return JSONResponse(status_code=409, content={"detail": f"Book with ISBN {exc.isbn} already exists", "code": "DUPLICATE_ISBN",},)

# Хранилище
BOOKS: list[dict] = []
CATEGORIES: list[dict] = []


# ═══════════════════════════════════════════════════════════
# КАТЕГОРИИ
# ═══════════════════════════════════════════════════════════
_books_id_counter = 1
_categories_id_counter = 1

@app.get("/categories")
def list_categories():
    """GET /categories — список всех категорий."""
    return CATEGORIES


@app.post("/categories", status_code=201)
def create_category(category: CategoryCreate):
    """POST /categories — создать категорию."""
    global _categories_id_counter
    new_category = {"id": _categories_id_counter, "name": category.name}
    CATEGORIES.append(new_category)
    _categories_id_counter += 1
    return new_category


# ═══════════════════════════════════════════════════════════
# CRUID КНИГ
# ═══════════════════════════════════════════════════════════


@app.get("/books")
def list_books(category_id: Optional[int] = None, year: Optional[int] = None):
    """GET /books — список книг. Опциональная фильтрация по category_id и year."""
    filtered_books = BOOKS
    if category_id is not None:
        filtered_books = [book for book in filtered_books if book.get("category_id") == category_id]
    if year is not None:
        filtered_books = [book for book in filtered_books if book["year"] == year]
    return filtered_books
@app.get("/books/search")
def search_books(query: str):
    """GET /books/search?query=... — поиск по title и author (case-insensitive)."""
    query_lower = query.lower()
    return [book for book in BOOKS if query_lower in book["title"].lower() or query_lower in book["author"].lower()]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    """GET /books/{id} — одна книга."""
    for book in BOOKS:
        if book["id"] == book_id:
            return book
    raise BookNotFoundException()


@app.post("/books", status_code=201)
def create_book(book: BookCreate):
    """POST /books — создать книгу.

    Проверять уникальность ISBN. Если дубликат — DuplicateIsbnException.
    """
    global _books_id_counter
    for b in BOOKS:
        if book.isbn == b["isbn"]:
            raise DuplicateIsbnException(isbn=book.isbn)
    new_book = {"id": _books_id_counter, **book.model_dump()}
    BOOKS.append(new_book)
    _books_id_counter += 1
    return new_book

@app.put("/books/{book_id}")
def update_book(book_id: int, book: BookCreate):
    """PUT /books/{id} — полностью обновить книгу."""
    for i,b in enumerate(BOOKS):
        if b["id"] == book_id:
            for other_book in BOOKS:
                if other_book["id"] != book_id and other_book["isbn"] == book.isbn:
                    raise DuplicateIsbnException(isbn=book.isbn)
            updated_book = {"id": book_id, **book.model_dump()}
            BOOKS[i] = updated_book
            return updated_book
    raise BookNotFoundException()


@app.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    """DELETE /books/{id} — удалить книгу."""
    for i, book in enumerate(BOOKS):
        if book["id"] == book_id:
            BOOKS.pop(i)
            return
    raise BookNotFoundException()