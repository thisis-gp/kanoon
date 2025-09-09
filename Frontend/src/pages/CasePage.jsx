"use client"

import { useState, useEffect } from "react"
import { useParams } from "react-router-dom"
import { useAuth } from "../context/auth-context"
import { Navbar } from "../components/navbar"
import { PDFViewerComponent } from "../components/pdf-viewer"
import { ChatInterface } from "../components/chat-interface"
import { CaseSummary } from "../components/case-summary"
import {
  SidebarProvider,
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarItem,
  SidebarGroup,
  SidebarTrigger,
} from "../components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs"
import { FileText, MessageSquare, FileSearch, AlertCircle } from "lucide-react"
import { getCaseById, initializeCaseChat, sendChatMessage } from "../utils/api"
import { saveChatMessage } from "../utils/firebase-helpers"
import { FAQSection } from "../components/faq-section"
import { Logo } from "../components/logo"

export default function CasePage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [caseData, setCaseData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState("document")
  const [chatInitialized, setChatInitialized] = useState(false)

  useEffect(() => {
    const loadCaseData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Load case details
        const data = await getCaseById(id)
        console.log("Loaded case data:", data)
        setCaseData(data)

        // Initialize chat in the background
        try {
          await initializeCaseChat(id)
          setChatInitialized(true)
        } catch (chatError) {
          console.error("Chat initialization error:", chatError)
          // Don't set main error for chat initialization failure
        }
      } catch (error) {
        console.error("Error fetching case data:", error)
        setError("Failed to load case data. Please try again later.")
      } finally {
        setIsLoading(false)
      }
    }

    loadCaseData()
  }, [id])

  const handleSendMessage = async (message) => {
    try {
      if (!chatInitialized) {
        // Try to initialize chat if not already done
        await initializeCaseChat(id)
        setChatInitialized(true)
      }

      // Send message to backend
      const response = await sendChatMessage(id, message)

      // Save to Firebase if user is logged in
      if (user) {
        const messageObj = {
          text: message,
          response: response.answer,
          timestamp: new Date().toISOString(),
        }

        await saveChatMessage(user.uid, id, messageObj)
      }

      return { text: response.answer }
    } catch (error) {
      console.error("Error sending message:", error)
      throw error
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {error ? (
        <div className="container mx-auto px-4 py-12 text-center">
          <div className="flex flex-col items-center justify-center">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <p className="text-destructive text-lg">{error}</p>
          </div>
        </div>
      ) : (
        <SidebarProvider>
          <Sidebar>

            <SidebarContent>
              <SidebarGroup title="Views">
                <SidebarItem
                  icon={FileText}
                  title="Document"
                  active={activeTab === "document"}
                  onClick={() => setActiveTab("document")}
                />
                <SidebarItem
                  icon={FileSearch}
                  title="Summary"
                  active={activeTab === "summary"}
                  onClick={() => setActiveTab("summary")}
                />
                <SidebarItem
                  icon={MessageSquare}
                  title="Chat"
                  active={activeTab === "chat"}
                  onClick={() => setActiveTab("chat")}
                />
                <SidebarItem
                  icon={FileSearch}
                  title="FAQ"
                  active={activeTab === "faq"}
                  onClick={() => setActiveTab("faq")}
                />
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>

          <div className="flex-1 overflow-hidden">
            <div className="flex h-15 items-center border-b px-4">
              <SidebarTrigger className="mr-2" />
              <h1 className="text-lg font-semibold">{isLoading ? "Loading..." : caseData?.title || "Case Details"}</h1>
            </div>

            <div className="h-[calc(100vh-3.5rem)] overflow-hidden">
              {/* Mobile Tabs */}
              <div className="md:hidden">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList className="w-full">
                    <TabsTrigger value="document" className="flex-1">
                      <FileText className="mr-2 h-4 w-4" />
                      Document
                    </TabsTrigger>
                    <TabsTrigger value="summary" className="flex-1">
                      <FileSearch className="mr-2 h-4 w-4" />
                      Summary
                    </TabsTrigger>
                    <TabsTrigger value="chat" className="flex-1">
                      <MessageSquare className="mr-2 h-4 w-4" />
                      Chat
                    </TabsTrigger>
                    <TabsTrigger value="faq" className="flex-1">
                      <FileSearch className="mr-2 h-4 w-4" />
                      FAQ
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="document" className="h-[calc(100vh-7rem)] overflow-hidden">
                    {caseData?.pdfUrl && <PDFViewerComponent pdfUrl={caseData.pdfUrl} />}
                  </TabsContent>

                  <TabsContent value="summary" className="h-[calc(100vh-7rem)] overflow-auto">
                    <CaseSummary caseData={caseData} isLoading={isLoading} />
                  </TabsContent>

                  <TabsContent value="chat" className="h-[calc(100vh-7rem)] overflow-hidden">
                    <ChatInterface caseId={id} onSendMessage={handleSendMessage} />
                  </TabsContent>

                  <TabsContent value="faq" className="h-[calc(100vh-7rem)] overflow-hidden">
                    <FAQSection
                      caseId={id}
                      caseData={caseData}
                      isLoading={isLoading}
                      onSendMessage={handleSendMessage}
                      onTabChange={setActiveTab}
                    />
                  </TabsContent>
                </Tabs>
              </div>

              {/* Desktop View */}
              <div className="hidden md:block h-full">
                {activeTab === "document" && caseData?.pdfUrl && <PDFViewerComponent pdfUrl={caseData.pdfUrl} />}

                {activeTab === "summary" && (
                  <div className="h-full overflow-auto">
                    <CaseSummary caseData={caseData} isLoading={isLoading} />
                  </div>
                )}

                {activeTab === "chat" && <ChatInterface caseId={id} onSendMessage={handleSendMessage} />}

                {activeTab === "faq" && (
                  <FAQSection
                    caseId={id}
                    caseData={caseData}
                    isLoading={isLoading}
                    onSendMessage={handleSendMessage}
                    onTabChange={setActiveTab}
                  />
                )}
              </div>
            </div>
          </div>
        </SidebarProvider>
      )}
    </div>
  )
}
