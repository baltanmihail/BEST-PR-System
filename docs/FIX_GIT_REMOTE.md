# 🔧 Быстрое решение: "Repository not found"

## ❌ Проблема

Вы видите ошибку:
```
remote: Repository not found.
fatal: repository 'https://github.com/yourusername/best-pr-system.git/' not found
```

## ✅ Решение

### Шаг 1: Удалить неправильный remote

```powershell
cd "BEST PR System"
git remote remove origin
```

### Шаг 2: Создать репозиторий на GitHub

1. Зайдите на [github.com](https://github.com)
2. Нажмите "+" → "New repository"
3. Название: `best-pr-system` (или любое другое)
4. **НЕ** добавляйте README, .gitignore или лицензию
5. Нажмите "Create repository"
6. **Скопируйте URL** репозитория (будет показан на странице)

### Шаг 3: Добавить правильный remote

```powershell
# ЗАМЕНИТЕ "ВАШ-USERNAME" на ваш реальный GitHub username!
git remote add origin https://github.com/ВАШ-USERNAME/best-pr-system.git
```

**Пример:**
```powershell
git remote add origin https://github.com/click/best-pr-system.git
```

### Шаг 4: Отправить код

```powershell
git branch -M main
git push -u origin main
```

---

## 📖 Подробная инструкция

См. [docs/GIT_SETUP.md](./docs/GIT_SETUP.md) для полной инструкции с решением всех проблем.

---

## ⚠️ Если нужна аутентификация

При `git push` GitHub может запросить логин/пароль:
- **Username**: ваш GitHub username
- **Password**: используйте **Personal Access Token** (не пароль!)

Как создать токен:
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Выберите `repo` (полный доступ)
4. Скопируйте токен и используйте как пароль
