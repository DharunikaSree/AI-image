import { SearchX, AlertTriangle } from "lucide-react";

export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card overflow-hidden">
          <div className="skeleton aspect-[4/5] w-full rounded-none" />
          <div className="space-y-2 p-4">
            <div className="skeleton h-3 w-1/3" />
            <div className="skeleton h-4 w-2/3" />
            <div className="skeleton h-4 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl2 border border-dashed border-charcoal-200 py-16 text-center dark:border-charcoal-700">
      <SearchX className="text-charcoal-300" size={32} />
      <div className="text-sm font-semibold text-charcoal-700 dark:text-white">{title}</div>
      {subtitle && <p className="max-w-sm text-sm text-charcoal-400">{subtitle}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl2 border border-rose-200 bg-rose-50 py-12 text-center dark:bg-charcoal-800 dark:border-rose-900">
      <AlertTriangle className="text-rose-500" size={28} />
      <p className="max-w-sm text-sm font-medium text-rose-700 dark:text-rose-300">{message}</p>
    </div>
  );
}
