import { createContext, useContext, forwardRef } from "react"
import { cn } from "../../lib/utils"

const TabsContext = createContext({ value: undefined, onValueChange: () => {} })

const Tabs = forwardRef(({ className, value, onValueChange, ...props }, ref) => (
  <TabsContext.Provider value={{ value, onValueChange }}>
    <div ref={ref} className={cn("relative", className)} {...props} />
  </TabsContext.Provider>
))
Tabs.displayName = "Tabs"

const TabsList = forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    role="tablist"
    className={cn(
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
      className,
    )}
    {...props}
  />
))
TabsList.displayName = "TabsList"

const TabsTrigger = forwardRef(({ className, value, ...props }, ref) => {
  const ctx = useContext(TabsContext)
  const active = ctx.value === value
  return (
    <button
      ref={ref}
      type="button"
      role="tab"
      id={`tab-${value}`}
      aria-selected={active}
      aria-controls={`panel-${value}`}
      data-state={active ? "active" : "inactive"}
      onClick={() => ctx.onValueChange?.(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-2 py-1.5 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm sm:px-3 sm:text-sm",
        className,
      )}
      {...props}
    />
  )
})
TabsTrigger.displayName = "TabsTrigger"

const TabsContent = forwardRef(({ className, value, ...props }, ref) => {
  const ctx = useContext(TabsContext)
  if (ctx.value !== value) return null
  return (
    <div
      ref={ref}
      role="tabpanel"
      id={`panel-${value}`}
      aria-labelledby={`tab-${value}`}
      className={cn("mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}
      {...props}
    />
  )
})
TabsContent.displayName = "TabsContent"

export { Tabs, TabsList, TabsTrigger, TabsContent }
