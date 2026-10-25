// Block 7: the shared-files panel, transcribed from the pre-1.0 desktop
// app's MainWindow.axaml
// (Border.card + DockPanel, L664-739) and its code-behind handlers.
// Every button drives the REAL share folder through the Rust commands
// (list_files / rename_file / delete_files / put_back / import_files).
import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { Msg } from "../Msg";
import { FilePlus, Pencil, RefreshCw, Trash2, Undo2 } from "lucide-react";
import { formatBytes, type T } from "../strings";

export type ShareFile = {
  name: string;
  size: number;
  full: string;
  origin: string | null;
  can_put_back: boolean;
};

export type FilesPayload = {
  path: string;
  missing: boolean;
  files: ShareFile[];
};

// Path.GetInvalidFileNameChars, the subset Windows refuses in a name.
const INVALID_CHARS = /[<>:"/\\|?*]/;

function namePreview(names: string[]): string {
  // MainWindow.NamePreview: five names, then "+N".
  const max = 5;
  const text = names.slice(0, max).join(", ");
  return names.length > max ? `${text} (+${names.length - max})` : text;
}

export function SharedFiles({
  t,
  lang,
  refreshKey,
}: {
  t: T;
  lang: "fr" | "en";
  refreshKey: number;
}) {
  const [payload, setPayload] = useState<FilesPayload | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [hint, setHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [dropping, setDropping] = useState(false);
  const anchorRef = useRef<number>(-1);
  const cardRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const p = await invoke<FilesPayload>("list_files");
      setPayload(p);
      // Drop selections whose file is gone (deleted elsewhere, renamed...).
      setSelected((prev) => {
        const live = new Set(p.files.map((f) => f.name));
        const next = prev.filter((n) => live.has(n));
        return next.length === prev.length ? prev : next;
      });
    } catch {
      /* keep the previous listing */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  // The desktop re-reads the folder on its 2 s poll; same rhythm here.
  useEffect(() => {
    const id = setInterval(() => void refresh(), 2000);
    return () => clearInterval(id);
  }, [refresh]);

  const files = payload?.files ?? [];
  const byName = (name: string) => files.find((f) => f.name === name);

  // ---------------------------------------------------------------- actions

  const importInto = useCallback(
    async (sources: string[], mode: "copy" | "move") => {
      setHint(t("Files.Adding"));
      setBusy(true);
      try {
        const r = await invoke<{ added: number; skipped: number; failed: number }>(
          "import_files",
          { sources, mode },
        );
        if (r.failed > 0) {
          await Msg.show(
            t("Files.AddTitle"),
            t("Files.AddFailed", String(r.added), String(r.failed)),
            t,
          );
        } else if (r.skipped > 0) {
          await Msg.show(
            t("Files.AddTitle"),
            t("Files.AddSkipped", String(r.added), String(r.skipped)),
            t,
          );
        }
      } catch (e) {
        await Msg.show(t("Err.Prefix"), String(e), t);
      } finally {
        setBusy(false);
        setHint("");
        await refresh();
      }
    },
    [refresh, t],
  );

  const addFiles = useCallback(async () => {
    if (payload?.missing) {
      await Msg.show(t("Label.SharedFiles"), t("Files.MissingFolder"), t);
      return;
    }
    const picked = await invoke<string[]>("pick_files");
    if (picked.length === 0) return;

    const choice = await Msg.choice(t("Files.AddTitle"), t("Files.CopyOrMove"), [
      { label: t("Files.Copy"), value: "copy", kind: "accent" },
      { label: t("Files.Move"), value: "move" },
      { label: t("Msg.Cancel"), value: "cancel" },
    ]);
    if (choice !== "copy" && choice !== "move") return;
    await importInto(picked, choice);
  }, [importInto, payload, t]);

  const renameSelected = useCallback(async () => {
    if (selected.length === 0) {
      await Msg.show(t("Label.SharedFiles"), t("Files.SelectAny"), t);
      return;
    }

    // --- one file: prompt with its own name -----------------------------
    if (selected.length === 1) {
      const file = byName(selected[0]);
      if (!file) return;
      const name = await Msg.input(
        t("Files.RenameTitle"),
        t("Files.RenamePrompt"),
        file.name,
        t,
      );
      if (name == null) return;
      const trimmed = name.trim();
      if (trimmed.length === 0 || trimmed === file.name) return;
      if (INVALID_CHARS.test(trimmed)) {
        await Msg.show(t("Files.RenameTitle"), t("Files.RenameInvalid"), t);
        return;
      }
      const result = await invoke<string>("rename_file", {
        old: file.name,
        new: trimmed,
      });
      if (result === "exists") {
        await Msg.show(t("Files.RenameTitle"), t("Files.RenameExists"), t);
      } else if (result === "ok") {
        setSelected([trimmed]);
      } else {
        await Msg.show(t("Files.RenameTitle"), `${t("Err.Prefix")} ${result}`, t);
      }
      await refresh();
      return;
    }

    // --- several files: one base name, numbered like the desktop -------
    const first = byName(selected[0]);
    const stem = first ? first.name.replace(/\.[^.]*$/, "") : "";
    const answer = await Msg.input(
      t("Files.RenameTitle"),
      t("Files.RenameBatchPrompt", String(selected.length)),
      stem,
      t,
    );
    if (answer == null) return;
    const base = answer.trim();
    if (base.length === 0) return;

    let failed = 0;
    const renamed: string[] = [];
    // Names taken by the other files plus the ones this batch already
    // assigned. A candidate equal to the file's OWN name is free (the
    // rename vacates it): checking the stale snapshot made the default
    // base name bump to " (2)" and collide on disk.
    const taken = new Set(files.map((f) => f.name.toLowerCase()));
    for (let i = 0; i < selected.length; i++) {
      const file = byName(selected[i]);
      if (!file) continue;
      taken.delete(file.name.toLowerCase());
      const dot = file.name.lastIndexOf(".");
      const ext = dot > 0 ? file.name.slice(dot) : "";
      let candidate = i === 0 ? `${base}${ext}` : `${base} (${i + 1})${ext}`;
      // UniquePath: a taken name gets " (2)", " (3)"... until free.
      let n = i + 1;
      while (taken.has(candidate.toLowerCase()) && n < 9999) {
        n++;
        candidate = `${base} (${n})${ext}`;
      }
      taken.add(candidate.toLowerCase());
      // Same name (the accepted default for the first file): nothing to
      // do - the Rust side would report "exists" on the case-insensitive
      // filesystem.
      if (candidate.toLowerCase() === file.name.toLowerCase()) {
        renamed.push(file.name);
        continue;
      }
      const result = await invoke<string>("rename_file", {
        old: file.name,
        new: candidate,
      });
      if (result === "ok") renamed.push(candidate);
      else failed++;
    }
    setSelected(renamed);
    if (failed > 0) {
      await Msg.show(
        t("Files.RenameTitle"),
        t("Files.RenameBatchFailed", String(failed)),
        t,
      );
    }
    await refresh();
  }, [files, refresh, selected, t]);

  const deleteSelected = useCallback(async () => {
    if (selected.length === 0) {
      await Msg.show(t("Label.SharedFiles"), t("Files.SelectAny"), t);
      return;
    }
    const answer = await Msg.confirm(
      t("Files.DeleteTitle"),
      t("Files.DeleteConfirm", String(selected.length), namePreview(selected)),
      t,
    );
    if (!answer) return;
    const failed = await invoke<number>("delete_files", { names: selected });
    setSelected([]);
    if (failed > 0) {
      await Msg.show(
        t("Files.DeleteTitle"),
        t("Files.DeleteFailed", String(failed)),
        t,
      );
    }
    await refresh();
  }, [refresh, selected, t]);

  const putBack = useCallback(
    async (file: ShareFile) => {
      const answer = await Msg.confirm(
        t("Files.PutBackTitle"),
        t("Files.PutBackConfirm", file.name, file.origin ?? ""),
        t,
      );
      if (!answer) return;
      try {
        await invoke<string>("put_back", { name: file.name });
      } catch (e) {
        await Msg.show(t("Files.PutBackTitle"), `${t("Err.Prefix")} ${e}`, t);
      }
      setSelected((prev) => prev.filter((n) => n !== file.name));
      await refresh();
    },
    [refresh, t],
  );

  const openFile = useCallback(
    async (file: ShareFile) => {
      try {
        await invoke("open_path", { path: file.full });
      } catch {
        await Msg.show(t("Label.SharedFiles"), t("Files.NotFound"), t);
        await refresh();
      }
    },
    [refresh, t],
  );

  // ------------------------------------------------------------ selection

  const clickRow = (index: number, name: string, e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      setSelected((prev) =>
        prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
      );
      anchorRef.current = index;
    } else if (e.shiftKey && anchorRef.current >= 0) {
      const [a, b] = [anchorRef.current, index].sort((x, y) => x - y);
      setSelected(files.slice(a, b + 1).map((f) => f.name));
    } else {
      setSelected([name]);
      anchorRef.current = index;
    }
  };

  // Web file-manager selection: a select-all box (with the in-between
  // state), a tick per row, and every selected row tinted accent.
  const allRef = useRef<HTMLInputElement>(null);
  const allChecked = files.length > 0 && selected.length === files.length;
  useEffect(() => {
    if (allRef.current) {
      allRef.current.indeterminate = selected.length > 0 && !allChecked;
    }
  }, [selected.length, allChecked]);

  const toggleAll = () => {
    setSelected(allChecked ? [] : files.map((f) => f.name));
  };

  const toggleOne = (name: string) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  };

  // --------------------------------------------------------- drag & drop

  useEffect(() => {
    // Tauri's own drag-drop (the webview suppresses the HTML5 one): the
    // event carries the real OS paths, which HTML5 never does. Drop
    // always COPIES (MainWindow.SharedFiles_Drop), folders included.
    const over = (x: number, y: number) => {
      const rect = cardRef.current?.getBoundingClientRect();
      if (!rect) return false;
      const dpr = window.devicePixelRatio || 1;
      const cx = x / dpr;
      const cy = y / dpr;
      return (
        cx >= rect.left && cx <= rect.right && cy >= rect.top && cy <= rect.bottom
      );
    };

    const unlisten = getCurrentWebview().onDragDropEvent((event) => {
      const pos = event.payload as { position?: { x: number; y: number } };
      if (event.payload.type === "leave") {
        setDropping(false);
        return;
      }
      if (event.payload.type === "enter" || event.payload.type === "over") {
        const p = pos.position;
        setDropping(!!p && over(p.x, p.y));
        return;
      }
      if (event.payload.type === "drop") {
        const p = pos.position;
        const inside = !!p && over(p.x, p.y);
        setDropping(false);
        const paths = (event.payload as { paths?: string[] }).paths ?? [];
        if (inside && paths.length > 0 && !busy) {
          void importInto(paths, "copy");
        }
      }
    });
    return () => {
      void unlisten.then((f) => f());
    };
  }, [busy, importInto]);

  // -------------------------------------------------------------- render

  return (
    <div
      ref={cardRef}
      className={`card flex min-h-0 flex-col ${dropping ? "dropping" : ""}`}
      style={{ margin: 0 }}
    >
      {/* Header: eyebrow + the drop hint where the eye already is. */}
      <div className="flex items-center justify-between">
        <span className="label" style={{ marginBottom: 0 }}>
          {t("Label.SharedFiles")}
        </span>
        <span className="label-hint">{t("Label.DropFilesHere")}</span>
      </div>

      {/* Actions (the desktop's WrapPanel), led by the select-all box. */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <label className="checkbox-wrap mr-1" title={t("Files.SelectAll")}>
          <input
            ref={allRef}
            type="checkbox"
            checked={allChecked}
            aria-label={t("Files.SelectAll")}
            onChange={toggleAll}
          />
          <span className="checkbox" />
        </label>
        <button
          type="button"
          className="btn-small"
          disabled={busy}
          onClick={() => void addFiles()}
        >
          <FilePlus size={14} aria-hidden />
          {t("Btn.AddFiles")}
        </button>
        <button
          type="button"
          className="btn-small"
          onClick={() => void renameSelected()}
        >
          <Pencil size={14} aria-hidden />
          {t("Btn.Rename")}
        </button>
        <button
          type="button"
          className="btn-small"
          onClick={() => void deleteSelected()}
        >
          <Trash2 size={14} aria-hidden />
          {t("Btn.Delete")}
        </button>
        <button
          type="button"
          className="btn-small"
          onClick={() => void refresh()}
        >
          <RefreshCw size={14} aria-hidden />
          {t("Btn.Refresh")}
        </button>
      </div>

      {payload?.missing ? (
        <p className="hint-danger mt-3 text-[11px]">{t("Files.MissingFolder")}</p>
      ) : null}
      {hint ? <p className="hint-muted mt-3 text-[11px]">{hint}</p> : null}

      {/* The list itself (rows fade in, like the ListBox style). */}
      <div className="filelist mt-1 min-h-0 flex-1 overflow-y-auto">
        {files.length === 0 ? (
          <p className="muted-text mt-2 text-center text-xs">{t("Files.Empty")}</p>
        ) : (
          files.map((file, i) => {
            const isSel = selected.includes(file.name);
            return (
              <div
                key={file.full}
                className={`file-row${isSel ? " selected" : ""}`}
                style={{ animationDelay: `${Math.min(i, 8) * 18}ms` }}
                onClick={(e) => clickRow(i, file.name, e)}
                onDoubleClick={() => void openFile(file)}
              >
                <label
                  className="checkbox-wrap mr-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={isSel}
                    aria-label={file.name}
                    onChange={() => toggleOne(file.name)}
                  />
                  <span className="checkbox sm" />
                </label>
                <span className="filename flex-1">{file.name}</span>
                {file.can_put_back ? (
                  <button
                    type="button"
                    className="btn-small mr-2 mt-0 px-2 py-1 text-[11px]"
                    onClick={(e) => {
                      e.stopPropagation();
                      void putBack(file);
                    }}
                  >
                    <Undo2 size={12} aria-hidden />
                    {t("Btn.PutBack")}
                  </button>
                ) : null}
                <span className="filesize">{formatBytes(file.size, lang)}</span>
              </div>
            );
          })
        )}
      </div>

      {/* Footer: folder path (the missing-folder warning sits above). */}
      <div className="mt-2">
        <div className="ellipsis text-[11px] text-text-dim">{payload?.path ?? ""}</div>
      </div>
    </div>
  );
}
