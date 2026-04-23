import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-display font-medium transition-all duration-200 focus-visible:outline-none disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default:
          'bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta hover:-translate-y-0.5',
        outline:
          'border border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 hover:bg-bg-2',
        ghost: 'text-fg-1 hover:bg-bg-2 hover:text-fg-0',
        magenta:
          'bg-magenta text-fg-0 shadow-sticker-magenta hover:-translate-y-0.5',
        cyan: 'bg-cyan text-bg-0 shadow-sticker-cyan hover:-translate-y-0.5',
      },
      size: {
        default: 'h-10 px-4 py-2 text-sm',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-12 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = 'Button';
