import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { HelpCircle, Send, Loader2, MessageSquare } from 'lucide-react'
import { tasksApi } from '../services/tasks'
import { TaskQuestion } from '../types/task_question'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { UserRole } from '../types/user'

interface TaskQuestionsProps {
  taskId: string
}

export default function TaskQuestions({ taskId }: TaskQuestionsProps) {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [newQuestion, setNewQuestion] = useState('')
  const [answeringId, setAnsweringId] = useState<string | null>(null)
  const [answerText, setAnswerText] = useState('')

  const isRegistered = !!user?.is_active
  
  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Загружаем вопросы
  const { data: questions, isLoading } = useQuery<TaskQuestion[]>({
    queryKey: ['task-questions', taskId],
    queryFn: () => tasksApi.getTaskQuestions(taskId),
    enabled: true, // Загружаем для всех
  })

  // Создание вопроса
  const createQuestionMutation = useMutation({
    mutationFn: (question: string) => tasksApi.createTaskQuestion(taskId, question),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task-questions', taskId] })
      setNewQuestion('')
    },
  })

  // Ответ на вопрос
  const answerQuestionMutation = useMutation({
    mutationFn: ({ questionId, answer }: { questionId: string; answer: string }) =>
      tasksApi.answerTaskQuestion(taskId, questionId, answer),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task-questions', taskId] })
      setAnsweringId(null)
      setAnswerText('')
    },
  })

  const handleSubmitQuestion = (e: React.FormEvent) => {
    e.preventDefault()
    if (newQuestion.trim() && isRegistered) {
      createQuestionMutation.mutate(newQuestion.trim())
    }
  }

  const handleAnswer = (questionId: string) => {
    if (answerText.trim()) {
      answerQuestionMutation.mutate({ questionId, answer: answerText.trim() })
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-best-primary" />
      </div>
    )
  }

  return (
    <div className="mb-4">
      <h4 className={`text-white font-semibold mb-3 flex items-center space-x-2 text-readable ${theme}`}>
        <HelpCircle className="h-4 w-4" />
        <span>Вопросы по задаче</span>
      </h4>

      {/* Форма для нового вопроса */}
      {isRegistered && (
        <form onSubmit={handleSubmitQuestion} className="mb-4">
          <div className="flex flex-col space-y-2">
            <textarea
              value={newQuestion}
              onChange={(e) => setNewQuestion(e.target.value)}
              placeholder="Задать вопрос по задаче..."
              className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} resize-none min-h-[80px]`}
              rows={3}
            />
            <button
              type="submit"
              disabled={!newQuestion.trim() || createQuestionMutation.isPending}
              className="flex items-center justify-center space-x-2 bg-best-primary text-white px-4 py-2 rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation"
            >
              {createQuestionMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Отправка...</span>
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  <span>Задать вопрос</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Список вопросов */}
      {questions && questions.length > 0 ? (
        <div className="space-y-4">
          {questions.map((question) => (
            <div
              key={question.id}
              className={`bg-white/5 rounded-lg p-4 border border-white/10 text-readable ${theme}`}
            >
              {/* Вопрос */}
              <div className="mb-2">
                <div className="flex items-start space-x-2">
                  <HelpCircle className="h-4 w-4 text-best-primary mt-1 flex-shrink-0" />
                  <div className="flex-1">
                    <p className={`text-white text-sm text-readable ${theme}`}>{question.question}</p>
                    {question.asked_by_name && (
                      <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
                        {question.asked_by_name} • {new Date(question.asked_at).toLocaleDateString('ru-RU')}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Ответ */}
              {question.is_answered && question.answer ? (
                <div className="mt-3 pl-6 border-l-2 border-best-primary/50">
                  <div className="flex items-start space-x-2">
                    <MessageSquare className="h-4 w-4 text-best-primary mt-1 flex-shrink-0" />
                    <div className="flex-1">
                      <p className={`text-white/90 text-sm text-readable ${theme}`}>{question.answer}</p>
                      {question.answered_by_name && (
                        <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
                          {question.answered_by_name} • {new Date(question.answered_at!).toLocaleDateString('ru-RU')}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : isCoordinator ? (
                <div className="mt-3 pl-6">
                  {answeringId === question.id ? (
                    <div className="space-y-2">
                      <textarea
                        value={answerText}
                        onChange={(e) => setAnswerText(e.target.value)}
                        placeholder="Введите ответ..."
                        className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} resize-none min-h-[60px] w-full`}
                        rows={2}
                      />
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleAnswer(question.id)}
                          disabled={!answerText.trim() || answerQuestionMutation.isPending}
                          className="flex items-center space-x-2 bg-best-primary text-white px-3 py-1.5 rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 text-sm touch-manipulation"
                        >
                          {answerQuestionMutation.isPending ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              <span>Отправка...</span>
                            </>
                          ) : (
                            <>
                              <Send className="h-3 w-3" />
                              <span>Отправить ответ</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => {
                            setAnsweringId(null)
                            setAnswerText('')
                          }}
                          className="px-3 py-1.5 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all text-sm touch-manipulation"
                        >
                          Отмена
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setAnsweringId(question.id)}
                      className="text-best-primary hover:text-best-primary/80 text-sm flex items-center space-x-1 touch-manipulation"
                    >
                      <MessageSquare className="h-3 w-3" />
                      <span>Ответить</span>
                    </button>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className={`text-white/60 text-sm text-readable ${theme}`}>
          {isRegistered ? 'Пока нет вопросов. Задайте первый вопрос!' : 'Пока нет вопросов.'}
        </p>
      )}
    </div>
  )
}
