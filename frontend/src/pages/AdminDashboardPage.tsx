import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import { Plus, Trash2, Pencil, Sparkles } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useToast } from "../context/ToastContext";
import type { Product } from "../types";

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

const EMPTY_FORM = {
  name: "", description: "", brand: "", category: "T-Shirt", subcategory: "", style: "Casual",
  color: "Black", pattern: "Solid", price: 999, discount_price: null as number | null,
  currency: "INR", image_url: "", product_url: "", platform: "Demo Store", availability: true, group_key: "",
};

export default function AdminDashboardPage() {
  const { push } = useToast();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);

  function loadDashboard() {
    api.get("/admin/dashboard").then((res) => setDashboard(res.data)).catch((err) => push(apiErrorMessage(err), "error"));
  }
  function loadProducts() {
    api.get("/admin/products").then((res) => setProducts(res.data)).catch((err) => push(apiErrorMessage(err), "error"));
  }

  useEffect(() => { loadDashboard(); loadProducts(); }, []);

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormOpen(true);
  }

  function openEdit(p: Product) {
    setForm({ ...p });
    setEditingId(p.id);
    setFormOpen(true);
  }

  async function submitForm() {
    try {
      if (editingId) {
        await api.put(`/admin/products/${editingId}`, form);
        push("Product updated", "success");
      } else {
        await api.post("/admin/products", form);
        push("Product created", "success");
      }
      setFormOpen(false);
      loadProducts();
      loadDashboard();
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  async function deleteProduct(id: number) {
    try {
      await api.delete(`/admin/products/${id}`);
      push("Product deleted", "info");
      loadProducts();
      loadDashboard();
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  async function generateEmbedding(id: number) {
    try {
      await api.post(`/admin/products/${id}/embedding`);
      push("Embedding generated", "success");
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Admin Dashboard</h1>

      {dashboard && (
        <>
          <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Total Users" value={dashboard.total_users} />
            <StatCard label="Total Products" value={dashboard.total_products} />
            <StatCard label="Total Searches" value={dashboard.total_searches} />
            <StatCard label="Avg. Confidence" value={`${dashboard.average_confidence}%`} />
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
                    {dashboard.popular_colors.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
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
      )}

      {/* Product management */}
      <div className="mt-14 flex items-center justify-between">
        <h2 className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">Product Management</h2>
        <button onClick={openCreate} className="btn-primary"><Plus size={16} /> Add Product</button>
      </div>

      <div className="mt-6 overflow-x-auto rounded-xl2 border border-charcoal-100 dark:border-charcoal-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-sand-50 text-xs uppercase tracking-wide text-charcoal-400 dark:bg-charcoal-800">
            <tr>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Price</th>
              <th className="px-4 py-3">Platform</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-t border-charcoal-100 dark:border-charcoal-700">
                <td className="flex items-center gap-3 px-4 py-3">
                  <img src={resolveAssetUrl(p.image_url)} className="h-10 w-10 rounded-lg object-cover" alt="" />
                  <span className="font-medium text-charcoal-800 dark:text-white">{p.name}</span>
                </td>
                <td className="px-4 py-3 text-charcoal-500 dark:text-charcoal-300">{p.category}</td>
                <td className="px-4 py-3 text-charcoal-500 dark:text-charcoal-300">₹{(p.discount_price ?? p.price).toFixed(0)}</td>
                <td className="px-4 py-3 text-charcoal-500 dark:text-charcoal-300">{p.platform}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => generateEmbedding(p.id)} title="Regenerate embedding" className="rounded-lg p-2 text-charcoal-400 hover:bg-sand-50"><Sparkles size={15} /></button>
                    <button onClick={() => openEdit(p)} className="rounded-lg p-2 text-charcoal-400 hover:bg-sand-50"><Pencil size={15} /></button>
                    <button onClick={() => deleteProduct(p.id)} className="rounded-lg p-2 text-charcoal-400 hover:bg-rose-50 hover:text-rose-500"><Trash2 size={15} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6" onClick={() => setFormOpen(false)}>
          <div className="card max-h-[85vh] w-full max-w-lg overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">{editingId ? "Edit Product" : "New Product"}</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <input className="input col-span-2" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className="input col-span-2" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <input className="input" placeholder="Brand" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} />
              <input className="input" placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              <input className="input" placeholder="Style" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} />
              <input className="input" placeholder="Color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
              <input className="input" type="number" placeholder="Price" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} />
              <input className="input" type="number" placeholder="Discount Price" value={form.discount_price ?? ""} onChange={(e) => setForm({ ...form, discount_price: e.target.value ? Number(e.target.value) : null })} />
              <input className="input" placeholder="Platform" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} />
              <input className="input" placeholder="Image URL (/uploads/...)" value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} />
              <input className="input col-span-2" placeholder="Product URL" value={form.product_url} onChange={(e) => setForm({ ...form, product_url: e.target.value })} />
              <input className="input col-span-2" placeholder="Group Key (for color variants)" value={form.group_key} onChange={(e) => setForm({ ...form, group_key: e.target.value })} />
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setFormOpen(false)} className="btn-secondary">Cancel</button>
              <button onClick={submitForm} className="btn-primary">{editingId ? "Save Changes" : "Create Product"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase tracking-wide text-charcoal-400">{label}</div>
      <div className="mt-1 font-display text-2xl font-semibold text-charcoal-900 dark:text-white">{value}</div>
    </div>
  );
}
