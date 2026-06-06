"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Button } from "@/components/ui/button";
import Link from "next/link";

// Fix Leaflet default icon issue with Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// Custom blue marker for listings
const listingIcon = L.divIcon({
  className: "",
  html: `<div style="
    background: #1F4E79;
    color: white;
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    width: 32px;
    height: 32px;
    border: 3px solid white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  "></div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

interface MapItem {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  average_rating?: number;
  lat?: number;
  lng?: number;
}

interface SearchMapProps {
  items: MapItem[];
  isLoading: boolean;
  onMarkerClick: (id: number) => void;
}

// Component to auto-fit bounds when items change
function FitBounds({ items }: { items: MapItem[] }) {
  const map = useMap();
  useEffect(() => {
    const validItems = items.filter(
      (i) => i.lat !== undefined && i.lng !== undefined
    );
    if (validItems.length === 0) return;
    if (validItems.length === 1) {
      map.setView([validItems[0].lat!, validItems[0].lng!], 14);
      return;
    }
    const bounds = L.latLngBounds(
      validItems.map((i) => [i.lat!, i.lng!])
    );
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [items, map]);
  return null;
}

export default function SearchMap({ items, isLoading, onMarkerClick }: SearchMapProps) {
  const validItems = items.filter(
    (i) => i.lat !== undefined && i.lng !== undefined && i.lat !== 0 && i.lng !== 0
  );

  // Default center — South Africa
  const defaultCenter: [number, number] = [-28.7282, 24.7435];

  if (isLoading) {
    return (
      <div className="w-full h-[600px] rounded-2xl bg-slate-100 animate-pulse flex items-center justify-center">
        <p className="text-slate-400">Loading map...</p>
      </div>
    );
  }

  if (validItems.length === 0) {
    return (
      <div className="w-full h-[600px] rounded-2xl bg-slate-100 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-500 font-medium">No listings to show on map</p>
          <p className="text-slate-400 text-sm mt-1">Try adjusting your search filters</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-[600px] rounded-2xl overflow-hidden border border-slate-200 shadow-sm">
      <MapContainer
        center={defaultCenter}
        zoom={12}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds items={validItems} />
        {validItems.map((item) => (
          <Marker
            key={item.id}
            position={[item.lat!, item.lng!]}
            icon={listingIcon}
          >
            <Popup>
              <div className="min-w-[200px]">
                <p className="font-semibold text-slate-900 text-sm mb-1 leading-snug">
                  {item.title}
                </p>
                <p className="text-xs text-slate-500 mb-2">{item.address}</p>
                <p className="text-sm font-bold text-slate-900 mb-3">
                  R{item.price_min.toLocaleString()}
                  {item.price_max > item.price_min &&
                    ` – R${item.price_max.toLocaleString()}`}
                  <span className="text-xs font-normal text-slate-400"> /month</span>
                </p>
                <Link
                  href={`/listings/${item.id}`}
                  className="block text-center text-xs font-semibold text-white bg-[#1F4E79] hover:bg-[#163a5e] rounded-lg py-1.5 px-3 transition-colors"
                >
                  View listing
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}