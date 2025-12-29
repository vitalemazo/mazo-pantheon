import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface KeyboardShortcutsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ShortcutItem {
  keys: string[];
  description: string;
}

interface ShortcutGroup {
  title: string;
  shortcuts: ShortcutItem[];
}

const shortcutGroups: ShortcutGroup[] = [
  {
    title: 'Panels',
    shortcuts: [
      { keys: ['⌘', 'B'], description: 'Toggle left sidebar (Flows)' },
      { keys: ['⌘', 'I'], description: 'Toggle right sidebar (Components)' },
      { keys: ['⌘', 'J'], description: 'Toggle bottom panel (Output & Research)' },
    ],
  },
  {
    title: 'Navigation',
    shortcuts: [
      { keys: ['⌘', ','], description: 'Open Settings' },
      { keys: ['⌘', 'O'], description: 'Fit view to canvas' },
    ],
  },
  {
    title: 'Editing',
    shortcuts: [
      { keys: ['⌘', 'S'], description: 'Save current flow' },
      { keys: ['⌘', 'Z'], description: 'Undo' },
      { keys: ['⌘', '⇧', 'Z'], description: 'Redo' },
    ],
  },
  {
    title: 'Canvas',
    shortcuts: [
      { keys: ['Delete'], description: 'Delete selected node' },
      { keys: ['Space'], description: 'Pan canvas (hold and drag)' },
      { keys: ['Scroll'], description: 'Zoom in/out' },
    ],
  },
];

function KeyboardKey({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 text-xs font-medium bg-muted border border-border rounded shadow-sm">
      {children}
    </kbd>
  );
}

export function KeyboardShortcutsDialog({
  open,
  onOpenChange,
}: KeyboardShortcutsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>
            Quick reference for keyboard shortcuts. Use ⌃ (Ctrl) on Windows/Linux.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-6 mt-4">
          {shortcutGroups.map((group) => (
            <div key={group.title}>
              <h3 className="text-sm font-semibold text-foreground mb-3">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between gap-4"
                  >
                    <span className="text-sm text-muted-foreground">
                      {shortcut.description}
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      {shortcut.keys.map((key, keyIndex) => (
                        <KeyboardKey key={keyIndex}>{key}</KeyboardKey>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            Tip: Hover over any button in the toolbar to see its keyboard shortcut
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
