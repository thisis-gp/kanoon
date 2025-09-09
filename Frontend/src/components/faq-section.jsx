"use client"

import { useState } from "react"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import { Skeleton } from "./ui/skeleton"
import { AlertCircle, ChevronDown } from "lucide-react"
import { Alert, AlertTitle, AlertDescription } from "./ui/alert"

// Predefined FAQ questions for legal cases
const PREDEFINED_QUESTIONS = [
  {
    id: "q1",
    question: "What is the main legal principle established in this case?",
    answer: null,
  },
  {
    id: "q2",
    question: "What were the key arguments presented by the plaintiff?",
    answer: null,
  },
  {
    id: "q3",
    question: "What were the key arguments presented by the defendant?",
    answer: null,
  },
  {
    id: "q4",
    question: "What precedents were cited in this ruling?",
    answer: null,
  },
  {
    id: "q5",
    question: "What are the potential implications of this ruling for future cases?",
    answer: null,
  },
  {
    id: "q6",
    question: "Were there any dissenting opinions in this case?",
    answer: null,
  },
  {
    id: "q7",
    question: "What statutory provisions were applied in this case?",
    answer: null,
  },
  {
    id: "q8",
    question: "What is the procedural history of this case?",
    answer: null,
  },
]

export function FAQSection({ caseId, caseData, isLoading, onSendMessage, onTabChange }) {
  const [questions, setQuestions] = useState(PREDEFINED_QUESTIONS)
  const [activeQuestion, setActiveQuestion] = useState(null)
  const [loadingQuestionId, setLoadingQuestionId] = useState(null)
  const [error, setError] = useState(null)

  // Function to fetch answer for a specific question
  const fetchAnswer = async (questionId, questionText) => {
    if (!caseId) return

    try {
      setLoadingQuestionId(questionId)
      setError(null)

      // Use the same onSendMessage function from the parent component
      const response = await onSendMessage(questionText)

      // Update the questions state with the answer
      setQuestions((prevQuestions) =>
        prevQuestions.map((q) => (q.id === questionId ? { ...q, answer: response.text } : q)),
      )
    } catch (err) {
      console.error("Error fetching answer:", err)
      setError("Failed to get an answer. Please try again.")
    } finally {
      setLoadingQuestionId(null)
    }
  }

  // Handle question click
  const handleQuestionClick = (questionId, questionText) => {
    // If we already have an answer, just toggle the accordion
    const question = questions.find((q) => q.id === questionId)

    if (question.answer) {
      setActiveQuestion(activeQuestion === questionId ? null : questionId)
      return
    }

    // Otherwise, fetch the answer
    fetchAnswer(questionId, questionText)
    setActiveQuestion(questionId)
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-3/4 mb-4" />
        <Skeleton className="h-24 w-full mb-4" />
        <Skeleton className="h-6 w-full mb-2" />
        <Skeleton className="h-6 w-full mb-2" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 h-full overflow-auto">
      <h2 className="text-2xl font-bold">Frequently Asked Questions</h2>

      <p className="text-muted-foreground">
        Get quick answers to common legal questions about this case without having to search through the entire
        document.
      </p>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Legal Questions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {questions.map((q) => (
              <div key={q.id} className="border rounded-md">
                <div
                  className={`flex justify-between items-center p-4 cursor-pointer ${
                    activeQuestion === q.id ? "bg-accent" : ""
                  }`}
                  onClick={() => handleQuestionClick(q.id, q.question)}
                >
                  <h3 className="font-medium">{q.question}</h3>
                  <ChevronDown
                    className={`h-4 w-4 transition-transform ${activeQuestion === q.id ? "transform rotate-180" : ""}`}
                  />
                </div>
                {activeQuestion === q.id && (
                  <div className="p-4 pt-0 border-t">
                    {loadingQuestionId === q.id ? (
                      <div className="py-4">
                        <div className="flex items-center space-x-2">
                          <div className="h-2 w-2 rounded-full bg-current animate-bounce" />
                          <div className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:0.2s]" />
                          <div className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:0.4s]" />
                        </div>
                      </div>
                    ) : (
                      <p className="py-2">{q.answer}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="mt-6">
        <h3 className="text-lg font-medium mb-2">Can't find what you're looking for?</h3>
        <p className="text-muted-foreground mb-4">
          If you have a specific question that's not covered here, you can ask it directly in the chat tab.
        </p>
        <Button onClick={() => onTabChange && onTabChange("chat")}>Go to Chat</Button>
      </div>
    </div>
  )
}
