// FileUploadFieldInput, adapted from
// opensourceui/components/inputs/file-upload-field-input.tsx
// Repainted with the app's exact glass look (the pre-1.0 Avalonia tokens).
// The send goes through Tauri invoke -> Rust -> engine /api/upload.
import { forwardRef, useCallback, useId, useRef, useState, type DragEvent } from "react";
import { ImagePlus, Plus, X } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { cn } from "../lib/cn";

type Entry = { id: string; name: string; size: number; file: File };

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export const FileUploadFieldInput = forwardRef<
  HTMLInputElement,
  {
    label?: string;
    onSent?: () => void;
  }
>(function FileUploadFieldInput({ label = "Envoyer un fichier", onSent }, ref) {
  const id = useId();
  const inputId = `${id}-file`;
  const localRef = useRef<HTMLInputElement | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const mergeRef = useCallback(
    (node: HTMLInputElement | null) => {
      localRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    },
    [ref],
  );

  const send = useCallback(
    async (incoming: File[]) => {
      if (!incoming.length) return;
      setBusy(true);
      setStatus("");
      const added: Entry[] = [];
      for (const file of incoming) {
        const entry: Entry = {
          id: `${file.name}-${file.size}-${file.lastModified}`,
          name: file.name,
          size: file.size,
          file,
        };
        added.push(entry);
        try {
          const buf = new Uint8Array(await file.arrayBuffer());
          const res = await invoke<Record<string, unknown>>("upload_file", {
            name: file.name,
            bytes: Array.from(buf),
          });
          setStatus(`✓ ${file.name} envoyé`);
          console.log("upload result", res);
        } catch (e) {
          setStatus(`✕ ${file.name}: ${String(e)}`);
        }
      }
      setEntries((prev) => [...prev, ...added]);
      setBusy(false);
      onSent?.();
    },
    [onSent],
  );

  const openPicker = () => localRef.current?.click();

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const list = e.dataTransfer.files;
      if (list?.length) void send(Array.from(list));
    },
    [send],
  );

  const remove = (rid: string) => setEntries((p) => p.filter((x) => x.id !== rid));

  const hasFiles = entries.length > 0;

  return (
    <div data-slot="file-upload" className="w-full">
      <label htmlFor={inputId} className="label mb-2 block w-fit">
        {label}
      </label>

      <input
        ref={mergeRef}
        id={inputId}
        type="file"
        className="sr-only"
        onChange={(e) => {
          const l = e.target.files;
          if (l?.length) void send(Array.from(l));
          e.target.value = "";
        }}
      />

      <div className="card !mb-0 !p-4">
        {!hasFiles ? (
          <div className="space-y-4">
            <div
              role="button"
              tabIndex={0}
              onClick={openPicker}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openPicker();
                }
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
              }}
              onDrop={handleDrop}
              className={cn(
                "relative aspect-[4/3] cursor-pointer overflow-hidden rounded-[14px] border transition-[border-color,background-color] duration-200",
                dragging
                  ? "border-accent bg-accent-soft/30"
                  : "border-white/10 bg-white/5 hover:bg-white/8",
              )}
            >
              {/* 3x3 grid + corner brackets, as in the source component */}
              <div aria-hidden className="absolute inset-0 grid grid-cols-3 grid-rows-3">
                {Array.from({ length: 9 }, (_, i) => (
                  <div key={i} className="border border-white/6" />
                ))}
              </div>
              <span aria-hidden className="absolute top-3 left-3 size-5 border-t-2 border-l-2 border-white/40" />
              <span aria-hidden className="absolute top-3 right-3 size-5 border-t-2 border-r-2 border-white/40" />
              <span aria-hidden className="absolute bottom-3 left-3 size-5 border-b-2 border-l-2 border-white/40" />
              <span aria-hidden className="absolute right-3 bottom-3 size-5 border-r-2 border-b-2 border-white/40" />

              <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
                <span
                  className={cn(
                    "mb-3 flex size-12 items-center justify-center rounded-[14px] border border-white/15 bg-glass-float text-text-muted transition-[border-color,transform] duration-200",
                    dragging && "scale-105 border-accent text-accent",
                  )}
                >
                  <ImagePlus size={22} strokeWidth={1.75} aria-hidden />
                </span>
                <span className="text-sm font-semibold text-text-title">
                  {dragging ? "Release to upload" : "Drop your file here"}
                </span>
                <span className="mt-1 text-xs text-text-muted">
                  Drag &amp; drop or click anywhere
                </span>
              </div>
            </div>

            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-faint">
                  {busy ? "Sending…" : "No file selected"}
                </p>
                <p className="mt-0.5 text-xs text-text-dim">ANY · max —</p>
              </div>
              <button
                type="button"
                onClick={openPicker}
                className="btn-accent shrink-0 px-4"
              >
                Choose file
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <ul className="space-y-2">
              {entries.map((e) => (
                <li
                  key={e.id}
                  className="flex items-center gap-3 rounded-[14px] border border-white/10 bg-white/5 p-2.5"
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] border border-white/15 bg-glass-float text-text-muted">
                    <ImagePlus size={16} strokeWidth={1.75} aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-text-primary">{e.name}</p>
                    <p className="mt-0.5 text-xs text-text-muted">{formatSize(e.size)}</p>
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${e.name}`}
                    onClick={() => remove(e.id)}
                    className="flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-[10px] border border-white/15 bg-glass-float text-text-muted transition-colors hover:text-text-title"
                  >
                    <X size={13} strokeWidth={2} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={openPicker}
              className="btn-small flex h-9 w-full items-center justify-center gap-2 border-dashed"
            >
              <Plus size={14} strokeWidth={2} aria-hidden />
              Add another file
            </button>
          </div>
        )}
      </div>

      {status ? <p className="mt-1.5 text-xs text-text-muted">{status}</p> : null}
    </div>
  );
});
