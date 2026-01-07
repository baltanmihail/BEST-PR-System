# BEST PR System - Frontend

Frontend приложение для системы управления PR-отделом BEST Москва.

## Технологии

- **React 18** + **TypeScript**
- **Vite** - быстрая сборка
- **Tailwind CSS** - стилизация
- **Shadcn/UI** - UI компоненты
- **React Router** - маршрутизация
- **Zustand** - управление состоянием
- **React Query** - работа с API
- **Lucide React** - иконки

## Установка

```bash
npm install
```

## Запуск

```bash
npm run dev
```

Приложение будет доступно по адресу: http://localhost:3000

## Сборка

```bash
npm run build
```

## Структура проекта

```
src/
├── components/     # Переиспользуемые компоненты
│   ├── layout/     # Layout компоненты (Header, Sidebar)
│   └── ui/          # UI компоненты из Shadcn
├── pages/          # Страницы приложения
├── hooks/          # Custom React hooks
├── store/          # Zustand stores
├── services/       # API сервисы
├── utils/          # Утилиты
└── types/          # TypeScript типы
```

## API

API доступен по адресу: https://best-pr-system.up.railway.app/api/v1
