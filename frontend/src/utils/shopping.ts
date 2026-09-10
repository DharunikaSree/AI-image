import type { DestinationType, ExternalLink, Product } from "../types";
import { isGenuineExternalUrl } from "./url";

export interface ResolvedShoppingDestination {
  url: string;
  storeName: string;
  destinationType: DestinationType;
  storeAvailable: boolean;
  cardCta: string;
  detailCta: string;
  explanatoryLabel: string;
}

export function normalizeDestinationType(type?: string | null): DestinationType {
  if (
    type === "exact_product" ||
    type === "official_store" ||
    type === "shopping_search" ||
    type === "fallback_search"
  ) {
    return type;
  }
  return "fallback_search";
}

export function getCardCta(destinationType: DestinationType): string {
  switch (destinationType) {
    case "exact_product":
      return "Shop Now ↗";
    case "official_store":
      return "Shop Brand ↗";
    case "shopping_search":
      return "Find Similar Products ↗";
    case "fallback_search":
    default:
      return "Search Online ↗";
  }
}

export function getDetailCta(destinationType: DestinationType): string {
  switch (destinationType) {
    case "exact_product":
      return "Shop Now";
    case "official_store":
      return "Shop Brand";
    case "shopping_search":
      return "Find Similar Products";
    case "fallback_search":
    default:
      return "Search Online";
  }
}

export function getExplanatoryLabel(destinationType: DestinationType): string {
  switch (destinationType) {
    case "exact_product":
      return "Verified retailer product";
    case "official_store":
      return "Official brand store";
    case "shopping_search":
    case "fallback_search":
    default:
      return "Search for this style online";
  }
}

export function resolveShoppingDestination(
  product: Product,
  storeUrl?: string | null,
  storeName?: string | null,
  destinationType?: string | null,
  storeAvailable?: boolean
): ResolvedShoppingDestination {
  // 1. Explicit props passed from recommendation API
  if (storeUrl && isGenuineExternalUrl(storeUrl)) {
    const dType = normalizeDestinationType(destinationType);
    const sName = storeName?.trim() || product.brand || product.platform || "Online Store";
    return {
      url: storeUrl,
      storeName: sName,
      destinationType: dType,
      storeAvailable: storeAvailable ?? (dType === "exact_product"),
      cardCta: getCardCta(dType),
      detailCta: getDetailCta(dType),
      explanatoryLabel: getExplanatoryLabel(dType),
    };
  }

  // 2. Check product.external_links
  if (product.external_links && Array.isArray(product.external_links) && product.external_links.length > 0) {
    let chosenLink: ExternalLink | null = null;

    // Prioritize exact_product / verified, then official_store, then search
    for (const link of product.external_links) {
      if (!isGenuineExternalUrl(link.url)) continue;
      const dType = (link.destination_type || "").toLowerCase();
      const vStatus = (link.verification_status || "").toLowerCase();

      if (dType === "exact_product" || vStatus === "verified") {
        chosenLink = link;
        break;
      }
      if (!chosenLink && (dType === "official_store" || vStatus === "official_store")) {
        chosenLink = link;
      } else if (!chosenLink) {
        chosenLink = link;
      }
    }

    if (chosenLink) {
      const dTypeRaw =
        chosenLink.destination_type ||
        (chosenLink.verification_status?.toLowerCase() === "verified"
          ? "exact_product"
          : chosenLink.verification_status?.toLowerCase() === "official_store"
          ? "official_store"
          : "shopping_search");
      const dType = normalizeDestinationType(dTypeRaw);
      const sName = chosenLink.store_name?.trim() || product.brand || "Store";
      const isAvail =
        chosenLink.availability_status === "available" || chosenLink.availability_status === "in_stock";

      return {
        url: chosenLink.url,
        storeName: sName,
        destinationType: dType,
        storeAvailable: isAvail,
        cardCta: getCardCta(dType),
        detailCta: getDetailCta(dType),
        explanatoryLabel: getExplanatoryLabel(dType),
      };
    }
  }

  // 3. Fallback to product.product_url if genuine
  if (isGenuineExternalUrl(product.product_url)) {
    const isGenericPlatform =
      !product.platform ||
      ["deepfashion", "catalog", "demo store", "demostore"].includes(product.platform.toLowerCase());
    const dType: DestinationType = isGenericPlatform ? "exact_product" : "official_store";
    const sName = isGenericPlatform ? (product.brand || "Store") : product.platform;

    return {
      url: product.product_url,
      storeName: sName,
      destinationType: dType,
      storeAvailable: product.availability ?? true,
      cardCta: getCardCta(dType),
      detailCta: getDetailCta(dType),
      explanatoryLabel: getExplanatoryLabel(dType),
    };
  }

  // 4. Safe dynamic search query fallback
  const query = [product.brand, product.color, product.category || product.name || "fashion"]
    .filter(Boolean)
    .join(" ");
  const fallbackUrl = `https://www.google.com/search?tbm=shop&q=${encodeURIComponent(query || "fashion")}`;
  return {
    url: fallbackUrl,
    storeName: "Google Shopping",
    destinationType: "fallback_search",
    storeAvailable: false,
    cardCta: getCardCta("fallback_search"),
    detailCta: getDetailCta("fallback_search"),
    explanatoryLabel: getExplanatoryLabel("fallback_search"),
  };
}
