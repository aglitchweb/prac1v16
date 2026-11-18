"""ПР1. Резервное копирование с ротацией и проверкой восстановления."""

import hashlib
import json
import shutil
import tarfile
import sys
import time

from datetime import datetime
from pathlib import Path

SOURCE = Path("company_data")      # что копируем
BACKUP_DIR = Path("backups")       # куда складываем архивы
KEEP_LAST = 6                      # вариант 16: хранить 6 последних копий


def sha256(path):
    """Считает SHA-256 файла."""
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)

    return h.hexdigest()


def make_manifest(folder):
    """Создаёт словарь: относительный путь файла -> его SHA-256."""
    return {
        str(p.relative_to(folder)): sha256(p)
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def get_manifest_path(archive):
    """Возвращает путь к JSON-файлу рядом с архивом."""
    return archive.with_suffix("").with_suffix(".json")


def create_backup():
    """Создаёт архив и JSON-манифест."""
    if not SOURCE.exists():
        print("[ERROR] Папка company_data не найдена. Сначала запустите make_test_data.py")
        return None

    BACKUP_DIR.mkdir(exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = BACKUP_DIR / f"backup_{stamp}.tar.gz"

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(SOURCE, arcname=SOURCE.name)

    manifest = {
        "created": stamp,
        "archive_sha256": sha256(archive),
        "files": make_manifest(SOURCE)
    }

    get_manifest_path(archive).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    original_size = sum(p.stat().st_size for p in SOURCE.rglob("*") if p.is_file())
    archive_size = archive.stat().st_size
    ratio = original_size / archive_size if archive_size else 0

    print(
        f"[OK] Создан {archive.name}, файлов: {len(manifest['files'])}, "
        f"размер: {archive_size / 1024:.1f} КБ, сжатие: {ratio:.2f} раз"
    )

    return archive


def rotate():
    """Оставляет только KEEP_LAST последних архивов и их манифесты."""
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))

    for old in archives[:-KEEP_LAST]:
        old.unlink()
        get_manifest_path(old).unlink(missing_ok=True)
        print(f"[ROTATE] Удалена старая копия {old.name}")


def verify_restore(archive):
    manifest_path = get_manifest_path(archive)

    if not manifest_path.exists():
        print("[FAIL] JSON-манифест не найден")
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))


    if sha256(archive) != manifest["archive_sha256"]:
        print("[FAIL] Архив повреждён: контрольная сумма не совпадает")
        return False

    tmp = Path("restore_test")
    shutil.rmtree(tmp, ignore_errors=True)

    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp, filter="data")
    except (tarfile.TarError, OSError) as error:
        print(f"[FAIL] Не удалось распаковать архив: {error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    restored = make_manifest(tmp / SOURCE.name)
    shutil.rmtree(tmp, ignore_errors=True)

    expected = manifest["files"]

    # Сравниваем списки файлов из манифеста и восстановленной папки.
    missing = sorted(set(expected) - set(restored))
    extra = sorted(set(restored) - set(expected))
    changed = sorted(
        name for name in set(expected) & set(restored)
        if expected[name] != restored[name]
    )

    if not missing and not extra and not changed:
        print(f"[OK] Восстановление проверено: {len(restored)} файлов совпадают")
        return True

    print("[FAIL] Восстановленные данные не совпадают с манифестом")

    for name in missing:
        print(f"[MISSING] Отсутствует файл: {name}")

    for name in extra:
        print(f"[EXTRA] Лишний файл: {name}")

    for name in changed:
        print(f"[CHANGED] Изменён хеш файла: {name}")

    return False


def restore(archive):
    """Восстанавливает company_data из архива и измеряет время."""
    # Не удаляем текущие данные, если архив или манифест не прошли проверку.
    if not verify_restore(archive):
        print("[FAIL] Восстановление не выполнено: сначала нужна исправная копия")
        return False

    start = time.perf_counter()

    shutil.rmtree(SOURCE, ignore_errors=True)

    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(Path("."), filter="data")
    except (tarfile.TarError, OSError) as error:
        print(f"[FAIL] Ошибка восстановления: {error}")
        return False

    elapsed = time.perf_counter() - start

    restored = make_manifest(SOURCE)
    manifest = json.loads(get_manifest_path(archive).read_text(encoding="utf-8"))

    if restored != manifest["files"]:
        print("[FAIL] После восстановления обнаружено несовпадение файлов")
        return False

    print(f"[OK] Данные восстановлены. Файлов: {len(restored)}")
    print(f"Время восстановления: {elapsed:.3f} секунд")
    return True


def main():
    # Сначала получаем список существующих архивов.
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))

    # Команда python backup.py restore восстанавливает последнюю копию.
    if len(sys.argv) > 1 and sys.argv[1].lower() == "restore":
        if not archives:
            print("[ERROR] Резервные копии не найдены")
            return
        restore(archives[-1])

    # Команда python backup.py verify проверяет последнюю копию.
    elif len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        if not archives:
            print("[ERROR] Резервные копии не найдены")
            return
        verify_restore(archives[-1])

    # Без аргумента создаётся новая резервная копия.
    else:
        archive = create_backup()

        if archive is not None:
            rotate()
            verify_restore(archive)


if __name__ == "__main__":
    main()
