"use client"

import { useState, useEffect } from "react"

const DESKTOP_QUERY = "(min-width: 768px)"

// Render one layout at a time so ids and chat state are not duplicated.
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(() => window.matchMedia(DESKTOP_QUERY).matches)
  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_QUERY)
    const onChange = (e) => setIsDesktop(e.matches)
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [])
  return isDesktop
}
import { useParams, Link } from "react-router-dom"
import { useAuth } from "../context/auth-context"
import { Navbar } from "../components/navbar"
import { PDFViewerComponent } from "../components/pdf-viewer"
import { ChatInterface } from "../components/chat-interface"
import { CaseSummary } from "../components/case-summary"
import CitationsPanel from "../components/citations-panel"
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
import { getCaseById, sendChatMessage, describeError } from "../utils/api"
import { displayTitle } from "../lib/utils"
import { saveChatMessage } from "../utils/firebase-helpers"
import { FAQSection } from "../components/faq-section"
import { Footer } from "../components/footer"
import { Disclaimer } from "../components/disclaimer"

export default function CasePage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [caseData, setCaseData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState("document")
  const isDesktop = useIsDesktop()

  useEffect(() => {
    const loadCaseData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Load case details
        const data = await getCaseById(id)
        setCaseData(data)
      } catch (error) {
        setError(describeError(error))
      } finally {
        setIsLoading(false)
      }
    }

    loadCaseData()
  }, [id])

  const handleSendMessage = async (message) => {
    try {
      // Send message to backend
      const response = await sendChatMessage(id, message)

      // Save to Firebase if user is logged in
      if (user) {
        const messageObj = {
          text: message,
          response: response.answer,
          timestamp: new Date().toISOString(),
        }

        saveChatMessage(user.uid, id, messageObj).catch(() => {})
      }

      return { text: response.answer }
    } catch (error) {
      throw new Error(describeError(error))
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />

      {error ? (
        <div className="container mx-auto px-4 py-12 text-center">
          <div className="flex flex-col items-center justify-center">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <p role="alert" className="text-destructive text-lg">{error}</p>
            <Link to="/" className="mt-4 text-indigo-300 underline">Back to search</Link>
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
            <div className="flex h-14 items-center border-b border-white/10 px-4">
              <SidebarTrigger className="mr-2" />
              <h1 className="text-lg font-semibold text-foreground truncate">
                {isLoading ? "Loading..." : displayTitle(caseData?.title, id)}
              </h1>
            </div>
            <div className="border-b border-white/10 px-4 py-2">
              <Disclaimer />
            </div>

            <div className="h-[calc(100dvh-11rem)] overflow-hidden">
              {!isDesktop && (
              <div>
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

                  <TabsContent value="document" className="h-[calc(100dvh-14rem)] overflow-hidden">
                    {caseData?.pdfUrl && <PDFViewerComponent pdfUrl={caseData.pdfUrl} />}
                  </TabsContent>

                  <TabsContent value="summary" className="h-[calc(100dvh-14rem)] overflow-auto">
                    <CaseSummary caseData={caseData} isLoading={isLoading} />
                    <div className="p-4 pt-0">
                      <CitationsPanel caseId={id} />
                    </div>
                  </TabsContent>

                  <TabsContent value="chat" className="h-[calc(100dvh-14rem)] overflow-hidden">
                    <ChatInterface caseId={id} onSendMessage={handleSendMessage} />
                  </TabsContent>

                  <TabsContent value="faq" className="h-[calc(100dvh-14rem)] overflow-hidden">
                    <FAQSection
                      caseId={id}
                      isLoading={isLoading}
                      onSendMessage={handleSendMessage}
                      onTabChange={setActiveTab}
                    />
                  </TabsContent>
                </Tabs>
              </div>
              )}

              {isDesktop && (
              <div className="h-full">
                {activeTab === "document" && caseData?.pdfUrl && <PDFViewerComponent pdfUrl={caseData.pdfUrl} />}

                {activeTab === "summary" && (
                  <div className="h-full overflow-auto">
                    <CaseSummary caseData={caseData} isLoading={isLoading} />
                    <div className="p-4 pt-0">
                      <CitationsPanel caseId={id} />
                    </div>
                  </div>
                )}

                {activeTab === "chat" && <ChatInterface caseId={id} onSendMessage={handleSendMessage} />}

                {activeTab === "faq" && (
                  <FAQSection
                    caseId={id}
                    isLoading={isLoading}
                    onSendMessage={handleSendMessage}
                    onTabChange={setActiveTab}
                  />
                )}
              </div>
              )}
            </div>
          </div>
        </SidebarProvider>
      )}
    </div>
  )
}
