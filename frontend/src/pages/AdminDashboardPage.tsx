import React, { useEffect, useState, useCallback, useRef, memo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from "recharts";
import {
  Plus,
  Trash2,
  Pencil,
  Sparkles,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RotateCcw,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useToast } from "../context/ToastContext";
import type { Product, PaginatedProductsResponse } from "../types";

interface DashboardData {
  total_users: number;
  total_products: number;
  total_searches: number;
  average_confidence: number;
  searches_per_day: { date: string; count: number }[];
  top_categories: { category: string; count: number }[];
  popular_colors: { color: string; count: number }[];
  price_distribution: { range: string; count: number }[];
}

const PIE_COLORS = ["#2A2622", "#A44E3F", "#CFBB9C", "#7C756D", "#D68C81", "#3D3833", "#E2D5C1", "#5A2A22"];

const CATEGORIES = [
  "All",
  "Shirt",
  "T-Shirt",
  "Shoes",
  "Dress",
  "Saree",
  "Kurta",
  "Jeans",
  "Trousers",
  "Shorts",
  "Jacket",
  "Sweater",
  "Hoodie",
  "Watches",
  "Handbags",
];

const EMPTY_FORM = {
  name: "",
  description: "",
  brand: "",
  category: "T-Shirt",
  subcategory: "",
  style: "Casual",
  color: "Black",
  pattern: "Solid",
  price: 999,
  discount_price: null as number | null,
  currency: "INR",
  image_url: "",
  product_url: "",
  platform: "Demo Store",
  availability: true,
  group_key: "",
};

// --------------------------------------------------------------------------
// 1. Memoized StatCard
// --------------------------------------------------------------------------
const StatCard = memo(function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase tracking-wide text-charcoal-400">{label}</div>
      <div className="mt-1 font-display text-2xl font-semibold text-charcoal-900 dark:text-white">{value}</div>
    </div>
  );
});

// --------------------------------------------------------------------------
// 2. Memoized Dashboard Analytics Section (Prevents chart re-renders on pagination)
// --------------------------------------------------------------------------
const DashboardAnalyticsView = memo(function DashboardAnalyticsView({
  dashboard,
}: {
  dashboard: DashboardData;
}) {
  return (
    <>
      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total Users" value={dashboard.total_users.toLocaleString()} />
        <StatCard label="Total Products" value={dashboard.total_products.toLocaleString()} />
        <StatCard label="Total Searches" value={dashboard.total_searches.toLocaleString()} />
        <StatCard label="Avg. ViT Confidence" value={`${dashboard.average_confidence}%`} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <div className="mb-4 text-sm font-semibold text-charcoal-800 dark:text-white">Searches Per Day</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dashboard.searches_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E6E4E2" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#A44E3F" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <div className="mb-4 text-sm font-semibold text-charcoal-800 dark:text-white">Top Categories Searched</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dashboard.top_categories} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#E6E4E2" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} width={80} />
              <Tooltip />
              <Bar dataKey="count" fill="#2A2622" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <div className="mb-4 text-sm font-semibold text-charcoal-800 dark:text-white">Popular Colors</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={dashboard.popular_colors} dataKey="count" nameKey="color" outerRadius={80} label>
                {dashboard.popular_colors.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <div className="mb-4 text-sm font-semibold text-charcoal-800 dark:text-white">Price Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dashboard.price_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E6E4E2" />
              <XAxis dataKey="range" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#D68C81" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
});

// --------------------------------------------------------------------------
// 3. Memoized Product Table Row
// --------------------------------------------------------------------------
const ProductTableRow = memo(function ProductTableRow({
  product: p,
  onEdit,
  onDelete,
  onGenerateEmbedding,
}: {
  product: Product;
  onEdit: (p: Product) => void;
  onDelete: (id: number) => void;
  onGenerateEmbedding: (id: number) => void;
}) {
  return (
    <tr className="hover:bg-sand-50/50 dark:hover:bg-charcoal-800/40 transition-colors">
      <td className="px-4 py-3 font-mono text-xs text-charcoal-400">#{p.id}</td>
      <td className="flex items-center gap-3 px-4 py-3">
        <img
          src={resolveAssetUrl(p.image_url)}
          className="h-10 w-10 shrink-0 rounded-lg object-cover bg-sand-100 dark:bg-charcoal-700"
          alt={p.name}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' fill='%23e5e7eb'/></svg>";
          }}
        />
        <div className="min-w-0 max-w-xs">
          <p className="truncate font-medium text-charcoal-800 dark:text-white" title={p.name}>
            {p.name}
          </p>
          <p className="truncate text-xs text-charcoal-400">
            {p.color} • {p.style}
          </p>
        </div>
      </td>
      <td className="px-4 py-3 text-charcoal-600 dark:text-charcoal-300">
        <span className="rounded-md bg-sand-100 px-2 py-0.5 text-xs dark:bg-charcoal-700">{p.category}</span>
      </td>
      <td className="px-4 py-3 text-charcoal-600 dark:text-charcoal-300">{p.brand || "—"}</td>
      <td className="px-4 py-3 font-medium text-charcoal-800 dark:text-white">
        ₹{(p.discount_price ?? p.price).toFixed(0)}
      </td>
      <td className="px-4 py-3 text-charcoal-500 dark:text-charcoal-400 text-xs">{p.platform}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex justify-end gap-1">
          <button
            onClick={() => onGenerateEmbedding(p.id)}
            title="Regenerate CLIP embedding"
            className="rounded-lg p-1.5 text-charcoal-400 hover:bg-sand-100 hover:text-terracotta-600 dark:hover:bg-charcoal-700"
          >
            <Sparkles size={15} />
          </button>
          <button
            onClick={() => onEdit(p)}
            title="Edit product"
            className="rounded-lg p-1.5 text-charcoal-400 hover:bg-sand-100 hover:text-charcoal-800 dark:hover:bg-charcoal-700 dark:hover:text-white"
          >
            <Pencil size={15} />
          </button>
          <button
            onClick={() => onDelete(p.id)}
            title="Delete product"
            className="rounded-lg p-1.5 text-charcoal-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </td>
    </tr>
  );
});

// --------------------------------------------------------------------------
// 4. Memoized Product Form Modal (Isolates form typing from main page)
// --------------------------------------------------------------------------
const ProductFormModal = memo(function ProductFormModal({
  isOpen,
  editingId,
  initialData,
  onClose,
  onSubmit,
}: {
  isOpen: boolean;
  editingId: number | null;
  initialData: typeof EMPTY_FORM;
  onClose: () => void;
  onSubmit: (formData: typeof EMPTY_FORM) => Promise<void>;
}) {
  const [formData, setFormData] = useState(initialData);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setFormData(initialData);
  }, [initialData]);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(formData);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="card max-h-[85vh] w-full max-w-lg overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
          {editingId ? "Edit Product" : "New Product"}
        </h3>
        <form onSubmit={handleSubmit}>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <input
              required
              className="input col-span-2"
              placeholder="Name *"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
            <input
              className="input col-span-2"
              placeholder="Description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
            <input
              className="input"
              placeholder="Brand"
              value={formData.brand}
              onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
            />
            <select
              className="input"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            >
              {CATEGORIES.filter((c) => c !== "All").map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Style"
              value={formData.style}
              onChange={(e) => setFormData({ ...formData, style: e.target.value })}
            />
            <input
              className="input"
              placeholder="Color"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Price (INR) *"
              value={formData.price}
              onChange={(e) => setFormData({ ...formData, price: Number(e.target.value) })}
            />
            <input
              className="input"
              type="number"
              placeholder="Discount Price (optional)"
              value={formData.discount_price ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, discount_price: e.target.value ? Number(e.target.value) : null })
              }
            />
            <input
              className="input"
              placeholder="Platform"
              value={formData.platform}
              onChange={(e) => setFormData({ ...formData, platform: e.target.value })}
            />
            <input
              className="input"
              placeholder="Image URL (/uploads/...)"
              value={formData.image_url}
              onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
            />
            <input
              className="input col-span-2"
              placeholder="Product URL"
              value={formData.product_url}
              onChange={(e) => setFormData({ ...formData, product_url: e.target.value })}
            />
            <input
              className="input col-span-2"
              placeholder="Group Key (for color variants)"
              value={formData.group_key}
              onChange={(e) => setFormData({ ...formData, group_key: e.target.value })}
            />
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting ? "Saving..." : editingId ? "Save Changes" : "Create Product"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});

// --------------------------------------------------------------------------
// 5. Main Admin Dashboard Page Component
// --------------------------------------------------------------------------
export default function AdminDashboardPage() {
  const { push } = useToast();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  // Pagination & Filter States
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState<number>(1);
  const [limit, setLimit] = useState<number>(20);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [category, setCategory] = useState<string>("All");

  // Status States
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modal Form State
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [modalInitialData, setModalInitialData] = useState(EMPTY_FORM);

  // Abort controller ref to cancel stale in-flight requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Debounce search input by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Load Dashboard Analytics (Isolated from product pagination)
  const loadDashboard = useCallback(() => {
    api
      .get<DashboardData>("/admin/dashboard")
      .then((res) => setDashboard(res.data))
      .catch((err) => push(apiErrorMessage(err), "error"));
  }, [push]);

  // Fetch paginated products with AbortController to prevent race conditions
  const fetchProducts = useCallback(
    async (targetPage: number, targetSearch: string, targetCategory: string, targetLimit: number) => {
      // Cancel previous in-flight request if still running
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: targetPage.toString(),
          limit: targetLimit.toString(),
        });
        if (targetSearch.trim()) {
          params.append("search", targetSearch.trim());
        }
        if (targetCategory && targetCategory !== "All") {
          params.append("category", targetCategory);
        }

        const res = await api.get<PaginatedProductsResponse>(`/admin/products?${params.toString()}`, {
          signal: controller.signal,
        });

        setProducts(res.data.items || []);
        setTotal(res.data.total);
        setPage(res.data.page);
        setLimit(res.data.limit);
        setTotalPages(res.data.total_pages);
      } catch (err: unknown) {
        // Ignore aborted requests
        if ((err as { name?: string })?.name === "CanceledError" || (err as { code?: string })?.code === "ERR_CANCELED") {
          return;
        }
        const msg = apiErrorMessage(err);
        setError(msg);
        push(msg, "error");
      } finally {
        setLoading(false);
      }
    },
    [push]
  );

  // Initial dashboard load on mount
  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  // Trigger product fetch whenever pagination or filter states change
  useEffect(() => {
    fetchProducts(page, debouncedSearch, category, limit);
  }, [page, debouncedSearch, category, limit, fetchProducts]);

  // Handlers
  const handleCategoryChange = useCallback((newCat: string) => {
    setPage(1);
    setCategory(newCat);
  }, []);

  const handleClearFilters = useCallback(() => {
    setSearchTerm("");
    setDebouncedSearch("");
    setCategory("All");
    setPage(1);
  }, []);

  const openCreate = useCallback(() => {
    setModalInitialData(EMPTY_FORM);
    setEditingId(null);
    setFormOpen(true);
  }, []);

  const openEdit = useCallback((p: Product) => {
    setModalInitialData({ ...p });
    setEditingId(p.id);
    setFormOpen(true);
  }, []);

  const handleFormSubmit = useCallback(
    async (formData: typeof EMPTY_FORM) => {
      try {
        if (editingId) {
          await api.put(`/admin/products/${editingId}`, formData);
          push("Product updated successfully", "success");
        } else {
          await api.post("/admin/products", formData);
          push("Product created successfully", "success");
        }
        setFormOpen(false);
        fetchProducts(page, debouncedSearch, category, limit);
        loadDashboard();
      } catch (err) {
        push(apiErrorMessage(err), "error");
        throw err;
      }
    },
    [editingId, page, debouncedSearch, category, limit, fetchProducts, loadDashboard, push]
  );

  const deleteProduct = useCallback(
    async (id: number) => {
      if (!window.confirm("Are you sure you want to delete this product?")) return;
      try {
        await api.delete(`/admin/products/${id}`);
        push("Product deleted", "info");
        const targetPage = products.length === 1 && page > 1 ? page - 1 : page;
        setPage(targetPage);
        fetchProducts(targetPage, debouncedSearch, category, limit);
        loadDashboard();
      } catch (err) {
        push(apiErrorMessage(err), "error");
      }
    },
    [products.length, page, debouncedSearch, category, limit, fetchProducts, loadDashboard, push]
  );

  const generateEmbedding = useCallback(
    async (id: number) => {
      try {
        await api.post(`/admin/products/${id}/embedding`);
        push("CLIP embedding generated successfully", "success");
      } catch (err) {
        push(apiErrorMessage(err), "error");
      }
    },
    [push]
  );

  const startRecordIndex = total === 0 ? 0 : (page - 1) * limit + 1;
  const endRecordIndex = Math.min(page * limit, total);

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Admin Dashboard</h1>
          <p className="mt-1 text-sm text-charcoal-500 dark:text-charcoal-300">
            System overview, visual search analytics, and catalog management.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={loadDashboard} className="btn-secondary flex items-center gap-2">
            <RotateCcw size={15} /> Refresh Analytics
          </button>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> Add Product
          </button>
        </div>
      </div>

      {dashboard && <DashboardAnalyticsView dashboard={dashboard} />}

      {/* Product Management Section */}
      <div className="mt-14">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">
              Product Catalog Management
            </h2>
            <p className="text-xs text-charcoal-500 dark:text-charcoal-300">
              Server-side paginated catalog ({total.toLocaleString()} total items in database)
            </p>
          </div>

          {/* Search and Category Filter Bar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex items-center">
              <input
                type="text"
                className="input h-10 w-48 pl-9 pr-8 text-xs sm:w-64"
                placeholder="Search products, brands..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <Search className="absolute left-3 text-charcoal-400" size={14} />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  className="absolute right-2 text-charcoal-400 hover:text-charcoal-700 dark:hover:text-white"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            <select
              value={category}
              onChange={(e) => handleCategoryChange(e.target.value)}
              className="input h-10 py-1 text-xs"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat === "All" ? "All Categories" : cat}
                </option>
              ))}
            </select>

            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setPage(1);
              }}
              className="input h-10 py-1 text-xs"
            >
              <option value={10}>10 / page</option>
              <option value={20}>20 / page</option>
              <option value={50}>50 / page</option>
              <option value={100}>100 / page</option>
            </select>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mt-4 flex items-center justify-between rounded-xl bg-rose-50 p-4 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
            <div className="flex items-center gap-2">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
            <button
              onClick={() => fetchProducts(page, debouncedSearch, category, limit)}
              className="font-medium underline hover:text-rose-900"
            >
              Retry
            </button>
          </div>
        )}

        {/* Active Filters Display */}
        {(debouncedSearch || category !== "All") && (
          <div className="mt-4 flex items-center gap-2 text-xs text-charcoal-600 dark:text-charcoal-300">
            <span>Filtered by:</span>
            {debouncedSearch && (
              <span className="inline-flex items-center gap-1 rounded-full bg-sand-200 px-2.5 py-0.5 font-medium text-charcoal-800 dark:bg-charcoal-700 dark:text-white">
                Query: "{debouncedSearch}"
              </span>
            )}
            {category !== "All" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-terracotta-100 px-2.5 py-0.5 font-medium text-terracotta-700 dark:bg-terracotta-950 dark:text-terracotta-300">
                Category: {category}
              </span>
            )}
            <button
              onClick={handleClearFilters}
              className="ml-2 font-medium text-terracotta-600 hover:underline dark:text-terracotta-400"
            >
              Reset Filters
            </button>
          </div>
        )}

        {/* Table Container */}
        <div className="relative mt-4 overflow-hidden rounded-xl border border-charcoal-100 dark:border-charcoal-700">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/50 backdrop-blur-[1px] dark:bg-charcoal-900/50 transition-opacity">
              <div className="flex items-center gap-2 text-sm font-medium text-charcoal-700 dark:text-white bg-white/80 dark:bg-charcoal-800/80 px-4 py-2 rounded-xl shadow-sm">
                <Loader2 className="animate-spin text-terracotta-500" size={16} />
                <span>Loading products...</span>
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-sand-50 text-xs uppercase tracking-wide text-charcoal-400 dark:bg-charcoal-800">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Brand</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Platform</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-100 dark:divide-charcoal-700">
                {products.length > 0 ? (
                  products.map((p) => (
                    <ProductTableRow
                      key={p.id}
                      product={p}
                      onEdit={openEdit}
                      onDelete={deleteProduct}
                      onGenerateEmbedding={generateEmbedding}
                    />
                  ))
                ) : !loading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center">
                      <p className="text-sm font-medium text-charcoal-600 dark:text-charcoal-300">
                        No products found matching your search.
                      </p>
                      <button
                        onClick={handleClearFilters}
                        className="mt-2 text-xs text-terracotta-600 hover:underline dark:text-terracotta-400"
                      >
                        Clear filters and show all products
                      </button>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {/* Pagination Navigation Footer */}
          <div className="flex flex-col gap-3 border-t border-charcoal-100 bg-sand-50/60 px-4 py-3 text-xs text-charcoal-600 sm:flex-row sm:items-center sm:justify-between dark:border-charcoal-700 dark:bg-charcoal-800/60 dark:text-charcoal-300">
            <div>
              Showing <span className="font-semibold text-charcoal-900 dark:text-white">{startRecordIndex.toLocaleString()}</span> to{" "}
              <span className="font-semibold text-charcoal-900 dark:text-white">{endRecordIndex.toLocaleString()}</span> of{" "}
              <span className="font-semibold text-charcoal-900 dark:text-white">{total.toLocaleString()}</span> items
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage(1)}
                disabled={page <= 1 || loading}
                title="First Page"
                className="rounded-lg border border-charcoal-200 p-1.5 disabled:opacity-40 hover:bg-white dark:border-charcoal-600 dark:hover:bg-charcoal-700 transition-colors"
              >
                <ChevronsLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1 || loading}
                title="Previous Page"
                className="rounded-lg border border-charcoal-200 p-1.5 disabled:opacity-40 hover:bg-white dark:border-charcoal-600 dark:hover:bg-charcoal-700 transition-colors"
              >
                <ChevronLeft size={14} />
              </button>

              <span className="px-2 font-medium text-charcoal-700 dark:text-white">
                Page {page} of {totalPages}
              </span>

              <button
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page >= totalPages || loading}
                title="Next Page"
                className="rounded-lg border border-charcoal-200 p-1.5 disabled:opacity-40 hover:bg-white dark:border-charcoal-600 dark:hover:bg-charcoal-700 transition-colors"
              >
                <ChevronRight size={14} />
              </button>
              <button
                onClick={() => setPage(totalPages)}
                disabled={page >= totalPages || loading}
                title="Last Page"
                className="rounded-lg border border-charcoal-200 p-1.5 disabled:opacity-40 hover:bg-white dark:border-charcoal-600 dark:hover:bg-charcoal-700 transition-colors"
              >
                <ChevronsRight size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Product Form Modal */}
      <ProductFormModal
        isOpen={formOpen}
        editingId={editingId}
        initialData={modalInitialData}
        onClose={() => setFormOpen(false)}
        onSubmit={handleFormSubmit}
      />
    </div>
  );
}
