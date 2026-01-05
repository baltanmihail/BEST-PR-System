# 🔧 Настройка Git и GitHub

## ⚠️ Проблема: "Repository not found"

Если вы видите ошибку:
```
remote: Repository not found.
fatal: repository 'https://github.com/yourusername/best-pr-system.git/' not found
```

Это значит, что вы использовали **пример URL** из документации. Нужно заменить его на **реальный URL** вашего репозитория.

---

## 🔍 Шаг 1: Проверка текущего remote

```powershell
git remote -v
```

Если видите `yourusername` в URL - это пример, его нужно удалить.

---

## 🗑️ Шаг 2: Удаление неправильного remote

```powershell
git remote remove origin
```

---

## 📦 Шаг 3: Создание репозитория на GitHub

### Вариант A: Через веб-интерфейс GitHub

1. Зайдите на [github.com](https://github.com)
2. Нажмите "+" → "New repository"
3. Название: `best-pr-system` (или любое другое)
4. **НЕ** добавляйте README, .gitignore или лицензию (у нас уже есть)
5. Нажмите "Create repository"
6. Скопируйте URL репозитория (будет показан на странице)

### Вариант B: Если репозиторий уже существует

1. Откройте ваш репозиторий на GitHub
2. Нажмите зеленую кнопку "Code"
3. Скопируйте HTTPS URL (например: `https://github.com/ваш-username/best-pr-system.git`)

---

## 🔗 Шаг 4: Добавление правильного remote

```powershell
# Замените URL на ваш реальный URL
git remote add origin https://github.com/ВАШ-USERNAME/best-pr-system.git
```

**Пример:**
```powershell
git remote add origin https://github.com/click/best-pr-system.git
```

---

## ✅ Шаг 5: Проверка и отправка

```powershell
# Проверить remote
git remote -v

# Должно показать ваш реальный URL

# Отправить код
git branch -M main
git push -u origin main
```

---

## 🔐 Если нужна аутентификация

### Через Personal Access Token (рекомендуется)

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Выберите права: `repo` (полный доступ к репозиториям)
4. Скопируйте токен
5. При `git push` используйте токен как пароль:
   - Username: ваш GitHub username
   - Password: токен (не ваш пароль!)

### Через SSH (альтернатива)

1. Создайте SSH ключ (если нет):
```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
```

2. Добавьте ключ в GitHub:
   - GitHub → Settings → SSH and GPG keys → New SSH key
   - Скопируйте содержимое `~/.ssh/id_ed25519.pub`

3. Используйте SSH URL:
```powershell
git remote set-url origin git@github.com:ВАШ-USERNAME/best-pr-system.git
```

---

## 📝 Полная последовательность команд

```powershell
# 1. Перейти в папку проекта
cd "BEST PR System"

# 2. Проверить remote (если есть)
git remote -v

# 3. Удалить неправильный remote (если нужно)
git remote remove origin

# 4. Добавить правильный remote (ЗАМЕНИТЕ URL!)
git remote add origin https://github.com/ВАШ-USERNAME/best-pr-system.git

# 5. Проверить
git remote -v

# 6. Отправить код
git branch -M main
git push -u origin main
```

---

## ❓ Частые вопросы

### Q: Как узнать мой GitHub username?
**A:** Зайдите на github.com, ваш username будет в URL: `https://github.com/ВАШ-USERNAME`

### Q: Можно ли использовать другой хостинг (GitLab, Bitbucket)?
**A:** Да! Просто используйте URL вашего репозитория:
```powershell
git remote add origin https://gitlab.com/username/best-pr-system.git
# или
git remote add origin https://bitbucket.org/username/best-pr-system.git
```

### Q: Что если я не хочу использовать GitHub?
**A:** Можно работать локально без remote:
```powershell
# Просто не добавляйте remote
# Все коммиты будут только локально
```

### Q: Ошибка "Permission denied"
**A:** 
- Проверьте, что вы авторизованы в GitHub
- Используйте Personal Access Token вместо пароля
- Или настройте SSH ключи

---

## 🎯 Быстрая справка

```powershell
# Проверить remote
git remote -v

# Удалить remote
git remote remove origin

# Добавить remote
git remote add origin <ВАШ-URL>

# Изменить существующий remote
git remote set-url origin <НОВЫЙ-URL>

# Отправить код
git push -u origin main
```
