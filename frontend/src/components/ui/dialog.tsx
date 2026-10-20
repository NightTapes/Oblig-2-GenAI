"use client";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { Button } from "./button";
export const Dialog = DialogPrimitive.Root;
export function DialogContent({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="dialog-overlay" />
      <DialogPrimitive.Content className="dialog-content">
        <DialogPrimitive.Title className="dialog-title">
          {title}
        </DialogPrimitive.Title>
        {description && (
          <DialogPrimitive.Description className="muted">
            {description}
          </DialogPrimitive.Description>
        )}
        <DialogPrimitive.Close asChild>
          <Button
            variant="ghost"
            size="icon"
            className="dialog-close"
            aria-label="Close dialog"
          >
            <X size={19} />
          </Button>
        </DialogPrimitive.Close>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
