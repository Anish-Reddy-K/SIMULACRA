import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-lg border text-sm font-medium whitespace-nowrap transition-[background-color,box-shadow,color] duration-150 outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:border-dashed disabled:opacity-60 pointer-coarse:min-h-11 pointer-coarse:min-w-11 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "border-primary bg-primary text-primary-foreground neu-raised-sm hover:brightness-110 active:neu-inset",
        outline:
          "border-border bg-card text-foreground neu-raised-sm hover:bg-muted active:neu-inset aria-pressed:neu-inset aria-pressed:bg-accent aria-pressed:text-accent-foreground",
        secondary:
          "border-border bg-muted text-foreground neu-inset hover:bg-secondary",
        ghost: "border-transparent text-foreground hover:bg-muted",
        destructive:
          "border-destructive bg-card text-destructive neu-raised-sm hover:bg-muted active:neu-inset",
        link: "border-transparent text-primary underline underline-offset-4 hover:no-underline",
      },
      size: {
        default: "h-10 px-4",
        xs: "h-8 px-2.5 text-xs",
        sm: "h-9 px-3",
        lg: "h-11 px-5 text-base",
        icon: "size-10",
        "icon-xs": "size-8",
        "icon-sm": "size-9",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
