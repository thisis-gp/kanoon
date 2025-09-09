"use client"

import { createContext, useContext, useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { PanelLeft, ChevronDown } from "lucide-react"
import { Button } from "./button"

const SidebarContext = createContext(null)

const useSidebar = () => {
  const context = useContext(SidebarContext)
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider")
  }
  return context
}

const SidebarProvider = ({ children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen)
  const [isMobile, setIsMobile] = useState(false)
  const [openMobile, setOpenMobile] = useState(false)

  // Check if we're on mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768)
    }

    checkMobile()
    window.addEventListener("resize", checkMobile)

    return () => {
      window.removeEventListener("resize", checkMobile)
    }
  }, [])

  // Toggle sidebar
  const toggleSidebar = () => {
    if (isMobile) {
      setOpenMobile(!openMobile)
    } else {
      setOpen(!open)
    }
  }

  return (
    <SidebarContext.Provider
      value={{
        open,
        setOpen,
        isMobile,
        openMobile,
        setOpenMobile,
        toggleSidebar,
        state: open ? "expanded" : "collapsed",
      }}
    >
      <div className="flex min-h-screen w-full">{children}</div>
    </SidebarContext.Provider>
  )
}

const Sidebar = ({ children, className, ...props }) => {
  const { isMobile, openMobile, setOpenMobile, state } = useSidebar()

  if (isMobile) {
    return (
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200 ease-in-out",
          openMobile ? "translate-x-0" : "-translate-x-full",
          className,
        )}
        {...props}
      >
        <div className="flex h-full flex-col bg-card shadow-lg">{children}</div>
        {openMobile && <div className="fixed inset-0 z-40 bg-black/50" onClick={() => setOpenMobile(false)} />}
      </div>
    )
  }

  return (
    <div
      data-state={state}
      className={cn(
        "relative flex h-screen w-64 flex-col bg-card transition-all duration-200 ease-in-out",
        state === "collapsed" && "w-16",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

const SidebarHeader = ({ className, ...props }) => {
  return <div className={cn("flex h-14 items-center border-b px-4", className)} {...props} />
}

const SidebarContent = ({ className, ...props }) => {
  return <div className={cn("flex-1 overflow-auto p-4", className)} {...props} />
}

const SidebarFooter = ({ className, ...props }) => {
  return <div className={cn("flex items-center border-t p-4", className)} {...props} />
}

const SidebarTrigger = ({ className, ...props }) => {
  const { toggleSidebar } = useSidebar()

  return (
    <Button variant="ghost" size="sm" className={cn("h-9 w-9 p-0", className)} onClick={toggleSidebar} {...props}>
      <PanelLeft className="h-5 w-5" />
      <span className="sr-only">Toggle Sidebar</span>
    </Button>
  )
}

const SidebarItem = ({ className, icon: Icon, title, active, ...props }) => {
  const { state } = useSidebar()

  return (
    <div
      className={cn(
        "flex cursor-pointer items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="mr-2 h-5 w-5" />}
      {(state === "expanded" || !Icon) && <span>{title}</span>}
    </div>
  )
}

const SidebarGroup = ({ className, title, children, ...props }) => {
  const { state } = useSidebar()
  const [open, setOpen] = useState(true)

  return (
    <div className={cn("mb-4", className)} {...props}>
      {title && state === "expanded" && (
        <div
          className="flex cursor-pointer items-center justify-between py-2 text-sm font-medium text-muted-foreground"
          onClick={() => setOpen(!open)}
        >
          {title}
          <ChevronDown className={cn("h-4 w-4 transition-transform", open ? "rotate-0" : "-rotate-90")} />
        </div>
      )}
      {(open || state === "collapsed") && <div className="space-y-1 pt-1">{children}</div>}
    </div>
  )
}

export {
  SidebarProvider,
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarTrigger,
  SidebarItem,
  SidebarGroup,
  useSidebar,
}

