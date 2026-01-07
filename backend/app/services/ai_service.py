"""
Сервис для ИИ-анализа предложений, концептов, сценариев и текстов
Поддерживает: GigaChat, OpenAI, Claude
"""
from typing import Dict, Optional
import json
import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """Провайдеры AI"""
    GIGACHAT = "gigachat"
    OPENAI = "openai"
    CLAUDE = "claude"
    NONE = "none"  # Заглушка


class AIService:
    """Сервис для работы с ИИ-анализом"""
    
    _provider: Optional[AIProvider] = None
    _api_key: Optional[str] = None
    
    @classmethod
    def _get_provider(cls) -> AIProvider:
        """Определяет провайдера из переменных окружения"""
        if cls._provider:
            return cls._provider
        
        provider_name = os.getenv("AI_PROVIDER", "none").lower()
        
        # Проверяем наличие API ключей
        if provider_name == "gigachat" and os.getenv("GIGACHAT_API_KEY"):
            cls._provider = AIProvider.GIGACHAT
            cls._api_key = os.getenv("GIGACHAT_API_KEY")
        elif provider_name == "openai" and os.getenv("OPENAI_API_KEY"):
            cls._provider = AIProvider.OPENAI
            cls._api_key = os.getenv("OPENAI_API_KEY")
        elif provider_name == "claude" and os.getenv("ANTHROPIC_API_KEY"):
            cls._provider = AIProvider.CLAUDE
            cls._api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            cls._provider = AIProvider.NONE
            logger.warning("AI provider not configured, using stub mode")
        
        return cls._provider
    
    @staticmethod
    async def _call_gigachat(prompt: str, system_prompt: str = "") -> str:
        """Вызов GigaChat API"""
        try:
            # Попробуем разные варианты импорта GigaChat
            try:
                from gigachat import GigaChat
            except ImportError:
                try:
                    from gigachat.client import GigaChat
                except ImportError:
                    raise ImportError("gigachat library not installed")
            
            # Инициализация клиента
            api_key = os.getenv("GIGACHAT_API_KEY")
            if not api_key:
                raise ValueError("GIGACHAT_API_KEY not set")
            
            # GigaChat может требовать авторизацию через OAuth
            # Проверьте документацию для вашего случая
            # Вариант 1: если ключ - это токен
            try:
                client = GigaChat(credentials=api_key, verify_ssl_certs=False)
            except:
                # Вариант 2: если нужна авторизация через OAuth
                # client = GigaChat(credentials=api_key, scope="GIGACHAT_API_PERS")
                # Или другой способ авторизации в зависимости от версии библиотеки
                raise ValueError("GigaChat authentication failed. Check credentials format.")
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Вызов API (зависит от версии библиотеки)
            try:
                response = client.chat(messages)
                # Разные варианты ответа в зависимости от версии
                if hasattr(response, 'choices'):
                    return response.choices[0].message.content
                elif hasattr(response, 'content'):
                    return response.content
                else:
                    return str(response)
            except Exception as e:
                logger.error(f"GigaChat chat call error: {e}")
                raise
            
        except ImportError:
            logger.error("gigachat library not installed. Install with: pip install gigachat")
            raise
        except Exception as e:
            logger.error(f"GigaChat API error: {e}")
            raise
    
    @staticmethod
    async def _call_openai(prompt: str, system_prompt: str = "") -> str:
        """Вызов OpenAI API"""
        try:
            import openai
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            
            client = openai.OpenAI(api_key=api_key)
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except ImportError:
            logger.error("openai library not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    @staticmethod
    async def _call_claude(prompt: str, system_prompt: str = "") -> str:
        """Вызов Claude API (Anthropic)"""
        try:
            from anthropic import Anthropic
            
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            
            client = Anthropic(api_key=api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            response = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=2000,
                system=system_prompt if system_prompt else None,
                messages=messages
            )
            
            return response.content[0].text
            
        except ImportError:
            logger.error("anthropic library not installed. Install with: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
    @staticmethod
    async def _call_ai(prompt: str, system_prompt: str = "") -> str:
        """Вызов AI API в зависимости от провайдера"""
        provider = AIService._get_provider()
        
        if provider == AIProvider.GIGACHAT:
            return await AIService._call_gigachat(prompt, system_prompt)
        elif provider == AIProvider.OPENAI:
            return await AIService._call_openai(prompt, system_prompt)
        elif provider == AIProvider.CLAUDE:
            return await AIService._call_claude(prompt, system_prompt)
        else:
            # Заглушка
            return "AI анализ недоступен. Настройте AI_PROVIDER и соответствующий API ключ."
    
    @staticmethod
    async def analyze_suggestion(
        suggestion_type: str,
        content: str,
        title: Optional[str] = None
    ) -> Dict:
        """
        Анализирует предложение (концепт, идею, сценарий, текст)
        
        Возвращает структурированный анализ с предложениями по улучшению
        """
        provider = AIService._get_provider()
        
        if provider == AIProvider.NONE:
            # Заглушка
            return AIService._stub_analyze_suggestion(suggestion_type, content, title)
        
        # Формируем промпт для AI
        system_prompt = """Ты опытный координатор PR-отдела, который анализирует предложения участников.
Твоя задача - дать конструктивную обратную связь в формате JSON:
{
    "summary": "краткое описание",
    "structure": "оценка структуры",
    "strengths": ["сильная сторона 1", "сильная сторона 2"],
    "improvements": ["предложение по улучшению 1", "предложение по улучшению 2"],
    "suggestions": ["дополнительная рекомендация 1", "дополнительная рекомендация 2"],
    "score": 7.5,
    "ready_for_use": false
}
Будь конструктивным и поддерживающим."""
        
        prompt = f"""Проанализируй {suggestion_type}:
Название: {title or 'без названия'}
Содержание:
{content}

Верни анализ в формате JSON."""
        
        try:
            ai_response = await AIService._call_ai(prompt, system_prompt)
            
            # Парсим JSON ответ
            # AI может вернуть JSON в markdown блоке или просто текст
            ai_response = ai_response.strip()
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(ai_response)
            return analysis
            
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            # Возвращаем заглушку при ошибке
            return AIService._stub_analyze_suggestion(suggestion_type, content, title)
    
    @staticmethod
    def _stub_analyze_suggestion(
        suggestion_type: str,
        content: str,
        title: Optional[str] = None
    ) -> Dict:
        """Заглушка для анализа (используется когда AI не настроен)"""
        analysis = {
            "summary": f"Краткое описание {suggestion_type}: {title or 'без названия'}",
            "structure": "Структура предложения",
            "strengths": [
                "Положительный момент 1",
                "Положительный момент 2"
            ],
            "improvements": [
                "Предложение по улучшению 1",
                "Предложение по улучшению 2"
            ],
            "suggestions": [
                "Дополнительная рекомендация 1",
                "Дополнительная рекомендация 2"
            ],
            "score": 7.5,
            "ready_for_use": False,
            "note": "⚠️ AI анализ не настроен. Используется базовая оценка."
        }
        
        # Простой анализ на основе ключевых слов
        if suggestion_type == "script":
            analysis["summary"] = f"Сценарий '{title or 'без названия}': {content[:100]}..."
            analysis["structure"] = "Проверьте структуру: начало, развитие, кульминация, развязка"
            if len(content) < 500:
                analysis["improvements"].append("Сценарий слишком короткий, рекомендуется расширить")
            if "действие" in content.lower() or "action" in content.lower():
                analysis["strengths"].append("Есть динамика в сценарии")
        
        elif suggestion_type == "text":
            analysis["summary"] = f"Текст поста: {content[:100]}..."
            analysis["structure"] = "Проверьте: заголовок, основной текст, призыв к действию"
            if len(content) < 100:
                analysis["improvements"].append("Текст слишком короткий для поста")
            if "#" in content or "@" in content:
                analysis["strengths"].append("Использованы хештеги/упоминания")
        
        elif suggestion_type == "concept":
            analysis["summary"] = f"Концепт: {title or 'без названия'}"
            analysis["structure"] = "Проверьте: идея, визуальное решение, целевая аудитория"
        
        elif suggestion_type == "idea":
            analysis["summary"] = f"Идея: {title or 'без названия'}"
            analysis["structure"] = "Проверьте: оригинальность, реализуемость, соответствие бренду"
        
        return analysis
    
    @staticmethod
    async def analyze_post_text(text: str) -> Dict:
        """
        Анализирует текст поста для SMM
        
        Проверяет структуру, читаемость, призыв к действию
        """
        provider = AIService._get_provider()
        
        if provider == AIProvider.NONE:
            # Заглушка
            return AIService._stub_analyze_post_text(text)
        
        system_prompt = """Ты SMM-эксперт, анализирующий тексты постов.
Верни анализ в формате JSON:
{
    "readability_score": 8.0,
    "has_cta": true,
    "hashtags_count": 3,
    "mentions_count": 1,
    "length_optimal": true,
    "suggestions": ["рекомендация 1", "рекомендация 2"]
}"""
        
        prompt = f"""Проанализируй текст поста для SMM:
{text}

Верни анализ в формате JSON."""
        
        try:
            ai_response = await AIService._call_ai(prompt, system_prompt)
            
            # Парсим JSON
            ai_response = ai_response.strip()
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(ai_response)
            return analysis
            
        except Exception as e:
            logger.error(f"AI post analysis error: {e}")
            return AIService._stub_analyze_post_text(text)
    
    @staticmethod
    def _stub_analyze_post_text(text: str) -> Dict:
        """Заглушка для анализа поста"""
        analysis = {
            "readability_score": 8.0,
            "has_cta": "присоединяйся" in text.lower() or "подписывайся" in text.lower(),
            "hashtags_count": text.count("#"),
            "mentions_count": text.count("@"),
            "length_optimal": 100 <= len(text) <= 2000,
            "suggestions": [],
            "note": "⚠️ AI анализ не настроен. Используется базовая оценка."
        }
        
        if len(text) < 100:
            analysis["suggestions"].append("Текст слишком короткий, рекомендуется расширить")
        if len(text) > 2000:
            analysis["suggestions"].append("Текст слишком длинный, рекомендуется сократить")
        if not analysis["has_cta"]:
            analysis["suggestions"].append("Рекомендуется добавить призыв к действию")
        if analysis["hashtags_count"] == 0:
            analysis["suggestions"].append("Рекомендуется добавить хештеги")
        
        return analysis
    
    @staticmethod
    async def structure_content(content: str, content_type: str) -> Dict:
        """
        Структурирует контент (разбивает на части, выделяет ключевые моменты)
        """
        provider = AIService._get_provider()
        
        if provider == AIProvider.NONE:
            # Заглушка
            return AIService._stub_structure_content(content)
        
        system_prompt = """Ты помощник, который структурирует контент.
Верни структуру в формате JSON:
{
    "parts": [{"type": "paragraph", "content": "...", "order": 1}],
    "key_points": ["ключевой момент 1", "ключевой момент 2"],
    "recommendations": ["рекомендация 1"]
}"""
        
        prompt = f"""Структурируй следующий {content_type}:
{content}

Верни структуру в формате JSON."""
        
        try:
            ai_response = await AIService._call_ai(prompt, system_prompt)
            
            # Парсим JSON
            ai_response = ai_response.strip()
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0].strip()
            
            structure = json.loads(ai_response)
            return structure
            
        except Exception as e:
            logger.error(f"AI structure error: {e}")
            return AIService._stub_structure_content(content)
    
    @staticmethod
    def _stub_structure_content(content: str) -> Dict:
        """Заглушка для структуризации"""
        structure = {
            "parts": [],
            "key_points": [],
            "recommendations": [],
            "note": "⚠️ AI структуризация не настроена. Используется базовая обработка."
        }
        
        # Разбиваем на абзацы
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        structure["parts"] = [
            {"type": "paragraph", "content": p, "order": i+1}
            for i, p in enumerate(paragraphs)
        ]
        
        # Извлекаем ключевые слова
        words = content.lower().split()
        common_words = {"и", "в", "на", "с", "для", "от", "по", "к", "а", "но", "или"}
        key_words = [w for w in words if len(w) > 4 and w not in common_words][:10]
        structure["key_points"] = list(set(key_words))
        
        return structure
