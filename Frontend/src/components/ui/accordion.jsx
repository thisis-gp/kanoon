"use client"
import { cn } from "../../lib/utils"
import { ChevronDown } from "lucide-react"

const Accordion = ({ className, type, ...props }) => {
  return <div className={cn("divide-y divide-border rounded-md border", className)} {...props} />
}

const AccordionItem = ({ className, ...props }) => {
  return <div className={cn("", className)} {...props} />
}

const AccordionTrigger = ({ className, children, isOpen, onClick, ...props }) => {
  return (
    <div
      className={cn(
        "flex cursor-pointer items-center justify-between py-4 px-5 text-sm transition-all hover:underline [&[data-state=open]>svg]:rotate-180",
        className,
      )}
      onClick={onClick}
      {...props}
    >
      {children}
      <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform duration-200", isOpen ? "rotate-180" : "")} />
    </div>
  )
}

const AccordionContent = ({ className, children, isOpen, ...props }) => {
  return isOpen ? (
    <div
      className={cn(
        "overflow-hidden px-5 pb-4 text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down",
        className,
      )}
      {...props}
    >
      <div className="pt-0">{children}</div>
    </div>
  ) : null
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
