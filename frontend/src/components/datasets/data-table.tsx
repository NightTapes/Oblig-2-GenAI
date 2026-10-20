"use client";
import { useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type SortingState,
  type ColumnDef,
} from "@tanstack/react-table";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import type { Profile, Rows } from "@/lib/schemas";
import { api } from "@/lib/api";
import { label } from "@/lib/utils";
import { Button } from "../ui/button";
export function DataTable({ profile }: { profile: Profile }) {
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [sorting, setSorting] = useState<SortingState>([]),
    [result, setResult] = useState<Rows | null>(null),
    [busy, setBusy] = useState(true),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError("");
    const params = new URLSearchParams({
      page: String(page),
      page_size: "25",
      search: query,
    });
    if (sorting[0]) {
      params.set("sort", sorting[0].id);
      params.set("descending", String(sorting[0].desc));
    }
    api
      .rows(profile.id, params, controller.signal)
      .then(setResult)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [profile.id, page, query, sorting, retry]);
  const columns = useMemo<ColumnDef<Record<string, unknown>>[]>(
    () =>
      profile.columns.map((c) => ({
        id: c.name,
        accessorFn: (row) => row[c.name],
        header: () => label(c.name),
        cell: (info) => {
          const value = info.getValue();
          return value === "" ? (
            <span className="cell-missing">missing</span>
          ) : (
            String(value ?? "")
          );
        },
        meta: { kind: c.kind },
      })),
    [profile],
  );
  const table = useReactTable({
    data: result?.rows || [],
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      setSorting(updater);
      setPage(1);
    },
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
  });
  return (
    <section className="table-card">
      <div className="table-toolbar">
        <div>
          <h3>Dataset records</h3>
          <p>Original values · Sort a column to explore</p>
        </div>
        <label className="search-field">
          <Search size={16} />
          <input
            aria-label="Search records"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search all columns…"
            maxLength={200}
          />
        </label>
      </div>
      {error ? (
        <div className="error-message" role="alert">
          {error}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRetry((v) => v + 1)}
          >
            Retry
          </Button>
        </div>
      ) : (
        <div className="table-scroll" aria-busy={busy}>
          <table>
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((header) => (
                    <th key={header.id}>
                      <button
                        onClick={header.column.getToggleSortingHandler()}
                        aria-label={`Sort by ${header.column.id}`}
                      >
                        <span>
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          <small>
                            {
                              profile.columns.find(
                                (c) => c.name === header.column.id,
                              )?.kind
                            }
                          </small>
                        </span>
                        {header.column.getIsSorted() === "asc" ? (
                          <ArrowUp size={13} />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ArrowDown size={13} />
                        ) : (
                          <ArrowUpDown size={13} />
                        )}
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!busy && !result?.rows.length && (
            <p className="table-empty">No records match your search.</p>
          )}
        </div>
      )}
      <div className="pagination">
        <span>
          {busy
            ? "Loading records…"
            : `${result?.total.toLocaleString() || 0} records · Page ${page} of ${Math.max(1, Math.ceil((result?.total || 0) / 25))}`}
        </span>
        <div>
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1 || busy}
            onClick={() => setPage((p) => p - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft size={15} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page * 25 >= (result?.total || 0) || busy}
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next page"
          >
            <ChevronRight size={15} />
          </Button>
        </div>
      </div>
    </section>
  );
}
