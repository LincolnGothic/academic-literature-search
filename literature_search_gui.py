#!/usr/bin/env python3
"""Desktop GUI for literature_search.py."""

from __future__ import annotations

import json
import queue
import re
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

import literature_search


class LiteratureSearchApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Academic Literature Search")
        self.geometry("1240x820")
        self.minsize(980, 680)

        self.operator_var = tk.StringVar(value="and")
        self.sort_var = tk.StringVar(value="relevance")
        self.max_results_var = tk.IntVar(value=5)
        self.timeout_var = tk.DoubleVar(value=20.0)
        self.pubmed_var = tk.BooleanVar(value=True)
        self.scholar_var = tk.BooleanVar(value=False)
        self.email_var = tk.StringVar(value="")
        self.api_key_var = tk.StringVar(value="")
        self.scholar_lang_var = tk.StringVar(value="en")
        self.status_var = tk.StringVar(value="Enter keywords or phrases, then start a search.")

        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.current_results: list[dict[str, Any]] = []
        self.current_payload: dict[str, Any] | None = None
        self.search_in_progress = False

        self._build_layout()
        self._apply_style()

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(bg="#f4f0e8")
        style.configure("TFrame", background="#f4f0e8")
        style.configure("TLabelframe", background="#f4f0e8")
        style.configure("TLabelframe.Label", background="#f4f0e8", foreground="#23313f")
        style.configure("TLabel", background="#f4f0e8", foreground="#23313f")
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 18))
        style.configure("Muted.TLabel", foreground="#4f5b66")
        style.configure("Accent.TButton", padding=(12, 8))

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Academic Literature Search", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Search PubMed and optionally try Google Scholar from a desktop app.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = ttk.LabelFrame(container, text="Search Setup", padding=14)
        controls.grid(row=1, column=0, sticky="nsew", pady=(14, 12))
        controls.columnconfigure(0, weight=3)
        controls.columnconfigure(1, weight=2)
        controls.rowconfigure(0, weight=1)

        query_frame = ttk.Frame(controls)
        query_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        query_frame.columnconfigure(0, weight=1)

        ttk.Label(
            query_frame,
            text="Keywords or phrases",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            query_frame,
            text="Enter one per line or separate them with commas.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 6))

        self.keyword_text = ScrolledText(query_frame, height=6, wrap="word", font=("Consolas", 11))
        self.keyword_text.grid(row=2, column=0, sticky="nsew")
        self.keyword_text.insert("1.0", "cancer\nimmunotherapy")

        options = ttk.Frame(controls)
        options.grid(row=0, column=1, sticky="nsew")
        for column in range(2):
            options.columnconfigure(column, weight=1)

        ttk.Label(options, text="Combine with").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.operator_var,
            values=["and", "or", "space"],
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 10))

        ttk.Label(options, text="Sort").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.sort_var,
            values=["relevance", "date"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=(4, 10))

        ttk.Label(options, text="Max results per source").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(options, from_=1, to=50, textvariable=self.max_results_var).grid(
            row=3, column=0, sticky="ew", padx=(0, 8), pady=(4, 10)
        )

        ttk.Label(options, text="Timeout (seconds)").grid(row=2, column=1, sticky="w")
        ttk.Spinbox(options, from_=5, to=120, increment=5, textvariable=self.timeout_var).grid(
            row=3, column=1, sticky="ew", pady=(4, 10)
        )

        ttk.Label(options, text="Sources").grid(row=4, column=0, sticky="w")
        source_frame = ttk.Frame(options)
        source_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 10))
        ttk.Checkbutton(source_frame, text="PubMed", variable=self.pubmed_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(source_frame, text="Google Scholar", variable=self.scholar_var).grid(
            row=0, column=1, sticky="w", padx=(12, 0)
        )

        ttk.Label(options, text="Scholar language").grid(row=6, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.scholar_lang_var).grid(
            row=7, column=0, sticky="ew", padx=(0, 8), pady=(4, 10)
        )

        ttk.Label(options, text="NCBI email").grid(row=6, column=1, sticky="w")
        ttk.Entry(options, textvariable=self.email_var).grid(row=7, column=1, sticky="ew", pady=(4, 10))

        ttk.Label(options, text="NCBI API key").grid(row=8, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.api_key_var, show="*").grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )

        action_bar = ttk.Frame(container)
        action_bar.grid(row=2, column=0, sticky="ew")
        action_bar.columnconfigure(1, weight=1)

        self.search_button = ttk.Button(
            action_bar,
            text="Search",
            command=self.start_search,
            style="Accent.TButton",
        )
        self.search_button.grid(row=0, column=0, sticky="w")

        ttk.Button(action_bar, text="Open Link", command=self.open_selected_link).grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )
        ttk.Button(action_bar, text="Export JSON", command=self.export_json).grid(
            row=0, column=3, sticky="e", padx=(8, 0)
        )
        ttk.Button(action_bar, text="Clear", command=self.clear_results).grid(
            row=0, column=4, sticky="e", padx=(8, 0)
        )

        body = ttk.Panedwindow(container, orient="horizontal")
        body.grid(row=3, column=0, sticky="nsew", pady=(12, 10))

        results_frame = ttk.LabelFrame(body, text="Results", padding=10)
        body.add(results_frame, weight=3)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        columns = ("source", "title", "journal", "published")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", selectmode="browse")
        self.results_tree.heading("source", text="Source")
        self.results_tree.heading("title", text="Title")
        self.results_tree.heading("journal", text="Journal")
        self.results_tree.heading("published", text="Published")
        self.results_tree.column("source", width=100, stretch=False)
        self.results_tree.column("title", width=430)
        self.results_tree.column("journal", width=220)
        self.results_tree.column("published", width=100, stretch=False)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        self.results_tree.bind("<<TreeviewSelect>>", self.on_result_selected)
        self.results_tree.bind("<Double-1>", lambda _event: self.open_selected_link())

        result_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=result_scroll.set)
        result_scroll.grid(row=0, column=1, sticky="ns")

        detail_frame = ttk.LabelFrame(body, text="Details", padding=10)
        body.add(detail_frame, weight=2)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        self.detail_text = ScrolledText(detail_frame, wrap="word", font=("Segoe UI", 10))
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        self.detail_text.configure(state="disabled")

        status_bar = ttk.Frame(container)
        status_bar.grid(row=4, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")

    def parse_keywords(self) -> list[str]:
        raw = self.keyword_text.get("1.0", "end").strip()
        if not raw:
            return []
        keywords = [part.strip() for part in re.split(r"[\r\n,]+", raw) if part.strip()]
        return keywords or [raw]

    def get_sources(self) -> list[str]:
        sources: list[str] = []
        if self.pubmed_var.get():
            sources.append("pubmed")
        if self.scholar_var.get():
            sources.append("scholar")
        return sources

    def start_search(self) -> None:
        if self.search_in_progress:
            return

        keywords = self.parse_keywords()
        if not keywords:
            messagebox.showwarning("Missing input", "Please enter at least one keyword or phrase.")
            return

        sources = self.get_sources()
        if not sources:
            messagebox.showwarning("Missing source", "Select at least one literature source.")
            return

        self.search_in_progress = True
        self.search_button.configure(state="disabled")
        self.status_var.set("Searching academic databases...")
        self.clear_results(reset_payload=False)

        worker = threading.Thread(
            target=self._search_worker,
            args=(keywords, sources),
            daemon=True,
        )
        worker.start()
        self.after(150, self._poll_queue)

    def _search_worker(self, keywords: list[str], sources: list[str]) -> None:
        try:
            query, results_by_source, errors, payload = literature_search.run_search(
                keywords=keywords,
                operator=self.operator_var.get(),
                sources=sources,
                max_results=max(1, int(self.max_results_var.get())),
                sort=self.sort_var.get(),
                timeout=float(self.timeout_var.get()),
                email=self.email_var.get().strip() or None,
                api_key=self.api_key_var.get().strip() or None,
                scholar_lang=self.scholar_lang_var.get().strip() or "en",
                snippet_length=900,
                quiet_errors=True,
            )
            flattened: list[dict[str, Any]] = []
            for source, items in results_by_source.items():
                for item in items:
                    flattened.append(
                        {
                            "source": source,
                            "title": item.title,
                            "journal": item.journal or "",
                            "published": item.published or "",
                            "authors": item.authors,
                            "snippet": item.snippet or "",
                            "url": item.url,
                            "doi": item.doi or "",
                            "query": query,
                        }
                    )
            self.result_queue.put(("success", {"results": flattened, "errors": errors, "payload": payload}))
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            kind, payload = self.result_queue.get_nowait()
        except queue.Empty:
            if self.search_in_progress:
                self.after(150, self._poll_queue)
            return

        self.search_in_progress = False
        self.search_button.configure(state="normal")

        if kind == "error":
            self.status_var.set("Search failed.")
            messagebox.showerror("Search failed", str(payload))
            return

        self.current_results = payload["results"]
        self.current_payload = payload["payload"]
        self.populate_results()

        total = len(self.current_results)
        errors = payload["errors"]
        if errors:
            warning_text = "\n".join(f"{source}: {message}" for source, message in errors.items())
            self.status_var.set(f"Search finished with {total} result(s) and {len(errors)} warning(s).")
            messagebox.showwarning("Source warnings", warning_text)
        else:
            self.status_var.set(f"Search finished with {total} result(s).")

    def populate_results(self) -> None:
        for item_id in self.results_tree.get_children():
            self.results_tree.delete(item_id)

        for index, item in enumerate(self.current_results):
            self.results_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(item["source"], item["title"], item["journal"], item["published"]),
            )

        if self.current_results:
            first = self.results_tree.get_children()[0]
            self.results_tree.selection_set(first)
            self.results_tree.focus(first)
            self.show_result_details(0)
        else:
            self.show_message_details("No results matched the current search.")

    def on_result_selected(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return
        self.show_result_details(int(selection[0]))

    def show_result_details(self, index: int) -> None:
        item = self.current_results[index]
        lines = [item["title"], ""]
        lines.append(f"Source: {item['source']}")
        if item["journal"]:
            lines.append(f"Journal: {item['journal']}")
        if item["published"]:
            lines.append(f"Published: {item['published']}")
        if item["authors"]:
            lines.append("Authors: " + ", ".join(item["authors"]))
        if item["doi"]:
            lines.append(f"DOI: {item['doi']}")
        lines.append(f"URL: {item['url']}")
        if item["snippet"]:
            lines.extend(["", "Summary", item["snippet"]])
        self.show_message_details("\n".join(lines))

    def show_message_details(self, message: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", message)
        self.detail_text.configure(state="disabled")

    def get_selected_result(self) -> dict[str, Any] | None:
        selection = self.results_tree.selection()
        if not selection:
            return None
        return self.current_results[int(selection[0])]

    def open_selected_link(self) -> None:
        selected = self.get_selected_result()
        if not selected:
            messagebox.showinfo("Open link", "Select a result first.")
            return
        webbrowser.open(selected["url"])

    def export_json(self) -> None:
        if not self.current_payload:
            messagebox.showinfo("Export JSON", "Run a search before exporting results.")
            return

        path = filedialog.asksaveasfilename(
            title="Save literature search results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="literature_results.json",
        )
        if not path:
            return

        with Path(path).open("w", encoding="utf-8") as handle:
            json.dump(self.current_payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        self.status_var.set(f"Saved results to {path}")

    def clear_results(self, reset_payload: bool = True) -> None:
        self.current_results = []
        if reset_payload:
            self.current_payload = None
        for item_id in self.results_tree.get_children():
            self.results_tree.delete(item_id)
        self.show_message_details("Search results will appear here.")


def main() -> None:
    app = LiteratureSearchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
