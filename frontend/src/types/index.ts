export interface User {
  id: number;
  name: string;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  brand: string;
  category: string;
  subcategory: string;
  style: string;
  color: string;
  pattern: string;
  price: number;
  discount_price: number | null;
  currency: string;
  image_url: string;
  product_url: string;
  platform: string;
  availability: boolean;
  group_key: string;
}

export interface ScoreBreakdown {
  visual_score: number;
  category_score: number;
  color_score: number;
  style_score: number;
  pattern_score: number;
  budget_score: number;
  preference_score: number;
  overall_score: number;
  reasons: string[];
}

export interface RecommendedProduct {
  product: Product;
  scores: ScoreBreakdown;
}

export interface DetectedAttributes {
  category: string;
  confidence: number;
  color: string;
  pattern: string;
  style: string;
  sleeve_type: string | null;
  neckline: string | null;
  gender_category: string | null;
  season: string | null;
}

export interface ImageSearchResponse {
  search_id: number;
  ai_mode: string;
  detected_items: DetectedAttributes[];
  best_matches: RecommendedProduct[];
  affordable_alternatives: RecommendedProduct[];
  similar_styles: RecommendedProduct[];
  color_variants: Product[];
  outfit: RecommendedProduct[] | null;
  outfit_total_price: number | null;
}

export interface SearchHistoryItem {
  id: number;
  image_path: string;
  detected_category: string;
  detected_style: string;
  detected_color: string;
  confidence: number;
  result_count: number;
  created_at: string;
}

export interface Preferences {
  preferred_styles: string[];
  preferred_colors: string[];
  preferred_categories: string[];
  budget_min: number;
  budget_max: number;
}
