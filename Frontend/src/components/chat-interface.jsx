"use client"

import { useState, useEffect, useRef } from "react"
import { useAuth } from "../context/auth-context"
import { Button } from "./ui/button"
import { Input } from "./ui/input"
import { Send, Volume2, VolumeX, Loader2 } from "lucide-react"
import { getChatHistory } from "../utils/firebase-helpers"

export function ChatInterface({ caseId, onSendMessage }) {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentAudio, setCurrentAudio] = useState(null)
  const messagesEndRef = useRef(null)

  // Load chat history
  useEffect(() => {
    const loadChatHistory = async () => {
      if (!user || !caseId) return

      try {
        const history = await getChatHistory(user.uid, caseId)
        if (history.length > 0) {
          const formattedMessages = history.map((item) => ({
            id: item.id,
            content: item.message,
            response: item.response,
            role: "user",
            timestamp: item.timestamp,
          }))
          setMessages(formattedMessages)
        }
      } catch (err) {
        console.error("Failed to load chat history:", err)
      }
    }

    loadChatHistory()
  }, [user, caseId])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Stop audio when component unmounts
  useEffect(() => {
    return () => {
      if (currentAudio) {
        currentAudio.pause()
        currentAudio.remove()
      }
    }
  }, [currentAudio])

  const handleSendMessage = async (e) => {
    e.preventDefault()

    if (!newMessage.trim() || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      content: newMessage,
      role: "user",
    }

    setMessages((prev) => [...prev, userMessage])
    setNewMessage("")
    setIsLoading(true)
    setError(null)

    try {
      const response = await onSendMessage(newMessage)

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        content: response.text,
        role: "assistant",
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      console.error("Error sending message:", err)
      setError("Failed to get a response. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuestionClick = (question) => {
    setNewMessage(question)
  }

  const handleTextToSpeech = async (text, messageId) => {
    // If already playing, stop it
    if (isPlaying && currentAudio) {
      currentAudio.pause()
      setCurrentAudio(null)
      setIsPlaying(false)
      return
    }

    try {
      // Create a new SpeechSynthesisUtterance
      const speech = new SpeechSynthesisUtterance(text)

      // Configure speech settings
      speech.rate = 1.0
      speech.pitch = 1.0
      speech.volume = 1.0

      // Get available voices and set a good one if available
      const voices = window.speechSynthesis.getVoices()
      const preferredVoice = voices.find(
        (voice) => voice.name.includes("Google") || voice.name.includes("Female") || voice.name.includes("US English"),
      )

      if (preferredVoice) {
        speech.voice = preferredVoice
      }

      // Set event handlers
      speech.onstart = () => setIsPlaying(true)
      speech.onend = () => {
        setIsPlaying(false)
        setCurrentAudio(null)
      }
      speech.onerror = () => {
        setIsPlaying(false)
        setCurrentAudio(null)
      }

      // Store reference to cancel if needed
      setCurrentAudio(speech)

      // Start speaking
      window.speechSynthesis.speak(speech)
    } catch (error) {
      console.error("Text-to-speech error:", error)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`rounded-lg px-4 py-2 max-w-[80%] ${
                  message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                <p className="text-base">{message.content}</p>
                {message.role === "assistant" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-6 w-6 p-0"
                    onClick={() => handleTextToSpeech(message.content, message.id)}
                  >
                    {isPlaying ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    <span className="sr-only">{isPlaying ? "Stop text-to-speech" : "Play text-to-speech"}</span>
                  </Button>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-muted px-4 py-2">
                <div className="flex items-center space-x-2">
                  <div className="h-2 w-2 rounded-full bg-current animate-bounce" />
                  <div className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:0.2s]" />
                  <div className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:0.4s]" />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-center">
              <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-2">{error}</div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t p-4">
        {/* <div className="mb-4">
          <h3 className="text-sm font-medium mb-2">Common Questions</h3>
          <div className="flex flex-wrap gap-2">
            {COMMON_QUESTIONS.map((question, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => handleQuestionClick(question)}
              >
                {question}
              </Button>
            ))}
          </div>
        </div> */}

        <form onSubmit={handleSendMessage} className="flex gap-2 items-center h-14">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Ask about this case..."
            className="flex-1 text-base placeholder:text-base h-full"
            disabled={isLoading}
          />
          <Button type="submit" size="icon" disabled={isLoading} className="h-full w-14">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-5 w-5" />}
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </div>
  )
}
