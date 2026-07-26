from html import escape

from models import Book, User


def safe(value) -> str:
    if value is None:
        return ""

    return escape(str(value))


def header_html(
    current_user: User | None
) -> str:
    if current_user:
        account_links = f"""
        <a href="/profile">
            {safe(current_user.username)}
        </a>

        <a href="/logout">
            Выйти
        </a>
        """
    else:
        account_links = """
        <a href="/login">
            Войти
        </a>

        <a href="/register">
            Регистрация
        </a>
        """

    return f"""
    <header class="header">
        <a class="logo" href="/">
            📚 BookHub
        </a>

        <nav>
            <a href="/">Главная</a>
            <a href="/#catalog">Каталог</a>
            <a href="/profile">Моя библиотека</a>
            {account_links}
        </nav>
    </header>
    """


def book_cover(book: Book) -> str:
    return f"""
    <img
        src="{safe(book.cover)}"
        alt="Обложка книги {safe(book.title)}"
        loading="lazy"
        onerror="
            this.onerror=null;
            this.src='https://placehold.co/400x600/1f6f5f/ffffff?text=Нет+обложки';
        "
    >
    """


def compact_book_card(book: Book) -> str:
    return f"""
    <article class="compact-card">
        <a href="/book/{book.id}">
            {book_cover(book)}
        </a>

        <div class="compact-info">
            <a
                class="compact-title"
                href="/book/{book.id}"
            >
                {safe(book.title)}
            </a>

            <p>
                {safe(book.author) or "Автор не указан"}
            </p>

            <a
                class="compact-link"
                href="/read/{book.id}"
            >
                Читать →
            </a>
        </div>
    </article>
    """


def catalog_book_card(
    book: Book,
    in_library: bool,
    logged_in: bool
) -> str:
    if not logged_in:
        library_button = """
        <a
            class="button button-secondary"
            href="/login"
        >
            Войти, чтобы добавить
        </a>
        """
    elif in_library:
        library_button = """
        <a
            class="button button-secondary"
            href="/profile"
        >
            ✓ В библиотеке
        </a>
        """
    else:
        library_button = f"""
        <a
            class="button button-secondary"
            href="/library/add/{book.id}"
        >
            ＋ Добавить
        </a>
        """

    return f"""
    <article
        class="card book-card"
        data-title="{safe(book.title).lower()}"
        data-author="{safe(book.author).lower()}"
        data-year="{safe(book.year)}"
    >
        <a href="/book/{book.id}">
            {book_cover(book)}
        </a>

        <div class="info">
            <p class="book-year">
                {safe(book.year) or "Год не указан"}
            </p>

            <h2>{safe(book.title)}</h2>

            <p>
                {safe(book.author) or "Автор не указан"}
            </p>

            <div class="card-actions">
                <a
                    class="button"
                    href="/book/{book.id}"
                >
                    Подробнее
                </a>

                {library_button}

                <a
                    class="button"
                    href="/read/{book.id}"
                >
                    Читать
                </a>
            </div>
        </div>
    </article>
    """


def render_home_page(
    books: list[Book],
    library_ids: set[int],
    history_books: list[Book],
    current_user: User | None
) -> str:
    sorted_by_year = sorted(
        books,
        key=lambda book: (
            book.year or 0,
            book.id or 0
        ),
        reverse=True
    )

    new_books = sorted_by_year[:6]

    new_books_html = "".join(
        compact_book_card(book)
        for book in new_books
    )

    continue_html = "".join(
        compact_book_card(book)
        for book in history_books
    )

    catalog_html = "".join(
        catalog_book_card(
            book=book,
            in_library=book.id in library_ids,
            logged_in=current_user is not None
        )
        for book in books
    )

    if continue_html and current_user:
        continue_section = f"""
        <section class="home-section">
            <div class="section-heading">
                <div>
                    <p class="eyebrow">
                        Ваша история
                    </p>

                    <h2>
                        Продолжить читать
                    </h2>
                </div>

                <a href="/profile">
                    Открыть профиль →
                </a>
            </div>

            <div class="horizontal-books">
                {continue_html}
            </div>
        </section>
        """
    else:
        continue_section = ""

    return f"""
    <!DOCTYPE html>

    <html lang="ru">
    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            BookHub — электронная библиотека
        </title>

        <link
            rel="stylesheet"
            href="/static/style.css"
        >

        <link
            rel="stylesheet"
            href="/static/catalog_fix.css"
        >
    </head>

    <body>
        {header_html(current_user)}

        <main class="container home-container">
            <section class="hero modern-hero">
                <div class="hero-content">
                    <p class="eyebrow">
                        Онлайн-библиотека
                    </p>

                    <h1>
                        Книги, которые действительно
                        можно читать
                    </h1>

                    <p>
                        Ищите произведения по названию
                        или автору, читайте полный текст
                        и сохраняйте книги в личном профиле.
                    </p>

                    <div class="hero-buttons">
                        <a
                            class="button hero-button"
                            href="#catalog"
                        >
                            Смотреть каталог
                        </a>

                        <a
                            class="button hero-outline"
                            href="/profile"
                        >
                            Моя библиотека
                        </a>
                    </div>
                </div>

                <div class="hero-stats">
                    <div>
                        <strong>{len(books)}</strong>
                        <span>читаемых книг</span>
                    </div>

                    <div>
                        <strong>{len(library_ids)}</strong>
                        <span>в вашей библиотеке</span>
                    </div>

                    <div>
                        <strong>{len(history_books)}</strong>
                        <span>недавно открыто</span>
                    </div>
                </div>
            </section>

            {continue_section}

            <section class="home-section">
                <div class="section-heading">
                    <div>
                        <p class="eyebrow">
                            Недавно выпущенные
                        </p>

                        <h2>
                            Новинки каталога
                        </h2>
                    </div>

                    <a href="#catalog">
                        Смотреть все →
                    </a>
                </div>

                <div class="horizontal-books">
                    {
                        new_books_html
                        or "<p>Книги пока не загружены.</p>"
                    }
                </div>
            </section>

            <section
                id="catalog"
                class="home-section"
            >
                <div class="catalog-header">
                    <div>
                        <p class="eyebrow">
                            Полная коллекция
                        </p>

                        <h2>
                            Каталог книг
                        </h2>
                    </div>

                    <div class="catalog-tools">
                        <input
                            id="searchInput"
                            class="catalog-search"
                            type="search"
                            placeholder="Название или автор"
                            autocomplete="off"
                        >

                        <select
                            id="yearFilter"
                            class="catalog-select"
                        >
                            <option value="all">
                                Все годы
                            </option>

                            <option value="new">
                                2000 и новее
                            </option>

                            <option value="classic">
                                Раньше 2000
                            </option>

                            <option value="unknown">
                                Год не указан
                            </option>
                        </select>
                    </div>
                </div>

                <section
                    id="booksContainer"
                    class="books"
                >
                    {
                        catalog_html
                        or "<p>Каталог пока пуст.</p>"
                    }
                </section>

                <section
                    id="emptySearch"
                    class="empty-state"
                    style="display:none;"
                >
                    <h2>Книги не найдены</h2>

                    <p>
                        Измените запрос или фильтр.
                    </p>
                </section>
            </section>
        </main>

        <script>
            const searchInput =
                document.getElementById("searchInput");

            const yearFilter =
                document.getElementById("yearFilter");

            const cards =
                document.querySelectorAll(".book-card");

            const emptySearch =
                document.getElementById("emptySearch");

            function normalize(value) {{
                return value
                    .toLowerCase()
                    .replaceAll("ё", "е")
                    .trim();
            }}

            function filterBooks() {{
                const query =
                    normalize(searchInput.value);

                const filterValue =
                    yearFilter.value;

                let visibleCount = 0;

                cards.forEach(function (card) {{
                    const title = normalize(
                        card.dataset.title || ""
                    );

                    const author = normalize(
                        card.dataset.author || ""
                    );

                    const yearText =
                        card.dataset.year || "";

                    const year =
                        Number(yearText || 0);

                    const matchesSearch =
                        title.includes(query)
                        || author.includes(query);

                    let matchesYear = true;

                    if (filterValue === "new") {{
                        matchesYear = year >= 2000;
                    }}

                    if (filterValue === "classic") {{
                        matchesYear =
                            year > 0 && year < 2000;
                    }}

                    if (filterValue === "unknown") {{
                        matchesYear =
                            !yearText || year === 0;
                    }}

                    const visible =
                        matchesSearch && matchesYear;

                    card.style.display =
                        visible ? "flex" : "none";

                    if (visible) {{
                        visibleCount += 1;
                    }}
                }});

                emptySearch.style.display =
                    (
                        cards.length > 0
                        && visibleCount === 0
                    )
                        ? "block"
                        : "none";
            }}

            searchInput.addEventListener(
                "input",
                filterBooks
            );

            yearFilter.addEventListener(
                "change",
                filterBooks
            );
        </script>
    </body>
    </html>
    """
