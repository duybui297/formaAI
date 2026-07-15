import * as React from "react"

import { cn } from "@/lib/utils"

const Checkbox = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<"input">
>(({ className, ...props }, ref) => {
  return (
    <input
      type="checkbox"
      ref={ref}
      className={cn(
        "h-4 w-4 rounded border-input text-primary focus:ring-primary accent-primary",
        className
      )}
      {...props}
    />
  )
})
Checkbox.displayName = "Checkbox"

export { Checkbox }
