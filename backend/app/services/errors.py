"""Ошибки предметной области (каждая соответствует ответу API, раздел 4.2 инструкции)."""

from __future__ import annotations


class AppError(Exception):
    """Базовая ошибка приложения с HTTP-статусом и машинным кодом."""

    status: int = 500
    code: str = "SERVER_ERROR"
    message: str = "Произошла ошибка на сервере. Повторите попытку позже."

    def __init__(self, message: str | None = None, fields: dict[str, str] | None = None) -> None:
        """Создаёт ошибку; ``message`` переопределяет текст по умолчанию."""
        super().__init__(message or self.message)
        self.message = message or type(self).message
        self.fields = fields


class UnauthorizedError(AppError):
    """Ошибка UNAUTHORIZED."""

    status = 401
    code = "UNAUTHORIZED"
    message = "Требуется вход в систему"


class ForbiddenError(AppError):
    """Ошибка FORBIDDEN."""

    status = 403
    code = "FORBIDDEN"
    message = "Недостаточно прав"


class NotFoundError(AppError):
    """Ошибка NOT_FOUND."""

    status = 404
    code = "NOT_FOUND"
    message = "Ресурс не найден"


class RequestTooLargeError(AppError):
    """Ошибка REQUEST_TOO_LARGE."""

    status = 413
    code = "REQUEST_TOO_LARGE"
    message = "Слишком большой запрос"


class ValidationFailedError(AppError):
    """Ошибка VALIDATION_ERROR."""

    status = 422
    code = "VALIDATION_ERROR"
    message = "Проверьте введённые данные"


class TooManyRequestsError(AppError):
    """Ошибка TOO_MANY_REQUESTS."""

    status = 429
    code = "TOO_MANY_REQUESTS"
    message = "Слишком много попыток. Повторите через несколько минут."


class EmailTakenError(AppError):
    """Ошибка EMAIL_TAKEN."""

    status = 409
    code = "EMAIL_TAKEN"
    message = "Пользователь с таким адресом уже зарегистрирован"


class InvalidCredentialsError(AppError):
    """Ошибка INVALID_CREDENTIALS."""

    status = 401
    code = "INVALID_CREDENTIALS"
    message = "Неверный адрес электронной почты или пароль"


class EmailNotConfirmedError(AppError):
    """Ошибка EMAIL_NOT_CONFIRMED."""

    status = 403
    code = "EMAIL_NOT_CONFIRMED"
    message = "Адрес электронной почты не подтверждён"


class TokenInvalidError(AppError):
    """Ошибка TOKEN_INVALID."""

    status = 400
    code = "TOKEN_INVALID"
    message = "Ссылка недействительна или устарела"


class ResumeNotFoundError(AppError):
    """Ошибка RESUME_NOT_FOUND."""

    status = 404
    code = "RESUME_NOT_FOUND"
    message = "Резюме не загружено"


class ResumeMissingForMatchError(AppError):
    """Ошибка RESUME_NOT_FOUND."""

    status = 409
    code = "RESUME_NOT_FOUND"
    message = "Для подбора вакансий загрузите резюме."


class ResumeNotReadyError(AppError):
    """Ошибка RESUME_NOT_READY."""

    status = 409
    code = "RESUME_NOT_READY"
    message = "Резюме ещё обрабатывается. Повторите подбор через несколько секунд."


class ResumeFailedError(AppError):
    """Ошибка RESUME_FAILED."""

    status = 409
    code = "RESUME_FAILED"
    message = "Не удалось обработать резюме. Загрузите другой файл в личном кабинете."


class UnsupportedFormatError(AppError):
    """Ошибка UNSUPPORTED_FORMAT."""

    status = 415
    code = "UNSUPPORTED_FORMAT"
    message = "Допустимы только файлы DOCX или PDF"


class FileTooLargeError(AppError):
    """Ошибка FILE_TOO_LARGE."""

    status = 413
    code = "FILE_TOO_LARGE"
    message = "Размер файла не должен превышать 5 МБ"


class PdfNoTextLayerError(AppError):
    """Ошибка PDF_NO_TEXT_LAYER."""

    status = 422
    code = "PDF_NO_TEXT_LAYER"
    message = "В файле нет текстового слоя. Загрузите PDF с выделяемым текстом или DOCX."


class FileUnreadableError(AppError):
    """Ошибка FILE_UNREADABLE."""

    status = 422
    code = "FILE_UNREADABLE"
    message = "Не удалось прочитать файл. Проверьте, что он не повреждён и не защищён паролем."


class ResumeEmptyError(AppError):
    """Ошибка RESUME_EMPTY."""

    status = 422
    code = "RESUME_EMPTY"
    message = "В файле не найден текст резюме."


class NoMatchRunError(AppError):
    """Ошибка NO_MATCH_RUN."""

    status = 404
    code = "NO_MATCH_RUN"
    message = "Подбор ещё не запускался"


class VacancyNotFoundError(AppError):
    """Ошибка VACANCY_NOT_FOUND."""

    status = 404
    code = "VACANCY_NOT_FOUND"
    message = "Вакансия не найдена"


class AlreadyInFavoritesError(AppError):
    """Ошибка ALREADY_IN_FAVORITES."""

    status = 409
    code = "ALREADY_IN_FAVORITES"
    message = "Вакансия уже в избранном"


class CollectionAlreadyRunningError(AppError):
    """Ошибка COLLECTION_ALREADY_RUNNING."""

    status = 409
    code = "COLLECTION_ALREADY_RUNNING"
    message = "Сбор вакансий уже выполняется"
