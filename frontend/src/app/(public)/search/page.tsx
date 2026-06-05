"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { accommodationsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { MapPin, Star, SlidersHorizontal, Search as SearchIcon, Building2, Loader2 } from "lucide-react";

const AMENITIES = [
  { id: "wifi", label: "Uncapped Wi-Fi" },
  { id: "backup_power", label: "Backup Power (Solar/Generator)" },
  { id: "security", label: "24/7 Security" },
  { id: "laundry", label: "Laundry Facilities" },
  { id: "furnished", label: "Fully Furnished" },
];

export default function SearchPage() {
  const searchParams = useSearchParams();
  const universityId = searchParams.get("university_id"); 
  
  // State for properties and loading
  const [properties, setProperties] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // State for filters
  const [priceRange, setPriceRange] = useState([5000]);

  // Fetch live data from your FastAPI backend
  useEffect(() => {
    const fetchProperties = async () => {
      setLoading(true);
      try {
        const uid = universityId ? parseInt(universityId, 10) : 1; 
        
        const response = await accommodationsApi.search({ 
          university_id: uid,
          // price_max: priceRange[0] // Uncomment when backend supports it
        });
        
        setProperties(response.data);
      } catch (error) {
        console.error("Failed to fetch properties:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchProperties();
  }, [universityId]);

  // The Filter UI extracted so we can use it in both Desktop and Mobile views
  const FilterSidebar = () => (
    <div className="space-y-8">
      {/* Price Range Filter */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Max Price (per month)</h3>
        <Slider
          defaultValue={[5000]}
          max={10000}
          step={100}
          value={priceRange}
          onValueChange={setPriceRange}
          className="mb-3"
        />
        <div className="flex justify-between text-sm text-gray-500 font-medium">
          <span>R 0</span>
          <span>R {priceRange[0].toLocaleString("en-ZA")}</span>
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Amenities Filter */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Must-have Amenities</h3>
        <div className="space-y-3">
          {AMENITIES.map((amenity) => (
            <div key={amenity.id} className="flex items-center space-x-3">
              <Checkbox id={amenity.id} className="border-gray-300 data-[state=checked]:bg-[#1F4E79] data-[state=checked]:border-[#1F4E79]" />
              <Label htmlFor={amenity.id} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                {amenity.label}
              </Label>
            </div>
          ))}
        </div>
      </div>

      <Button className="w-full bg-[#1F4E79] hover:bg-[#163a5e] text-white">
        Apply Filters
      </Button>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F8F9FA] pb-20">
      
      {/* ── Search Header ── */}
      <div className="bg-white border-b border-gray-200 sticky top-16 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 w-full max-w-lg bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#1F4E79] focus-within:bg-white transition-all">
            <SearchIcon className="h-5 w-5 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search by neighborhood or street..." 
              className="bg-transparent border-none outline-none w-full text-sm text-gray-800 placeholder:text-gray-400"
            />
          </div>

          {/* Mobile Filter Sheet Trigger */}
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" className="lg:hidden shrink-0 flex items-center gap-2 rounded-xl">
                <SlidersHorizontal className="h-4 w-4" />
                Filters
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-full sm:w-[400px]">
              <SheetHeader className="mb-8 text-left">
                <SheetTitle className="text-xl font-bold">Filters</SheetTitle>
              </SheetHeader>
              <FilterSidebar />
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 pt-8">
        <div className="flex flex-col lg:flex-row gap-10">
          
          {/* ── Desktop Sidebar (Hidden on Mobile) ── */}
          <aside className="hidden lg:block w-72 shrink-0">
            <div className="bg-white p-6 rounded-2xl border border-gray-200 sticky top-40">
              <div className="flex items-center gap-2 mb-6">
                <SlidersHorizontal className="h-5 w-5 text-[#1F4E79]" />
                <h2 className="text-lg font-bold text-gray-900">Filters</h2>
              </div>
              <FilterSidebar />
            </div>
          </aside>

          {/* ── Results Grid ── */}
          <main className="flex-1">
            <div className="mb-6 flex items-center justify-between">
              <h1 className="text-2xl font-bold text-gray-900">
                {universityId === "1" ? "Properties near Sol Plaatje" : "All Properties"}
              </h1>
              <span className="text-sm font-medium text-gray-500">
                {!loading && `${properties.length} results`}
              </span>
            </div>

            {/* Handle Loading State */}
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                <Loader2 className="h-8 w-8 animate-spin text-[#1F4E79] mb-4" />
                <p>Finding the best accommodations...</p>
              </div>
            ) : properties.length === 0 ? (
              /* Handle Empty State */
              <div className="text-center py-20 bg-white rounded-2xl border border-gray-200">
                <div className="h-16 w-16 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Building2 className="h-8 w-8" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">No properties found</h3>
                <p className="text-gray-500">Try adjusting your filters or searching a different area.</p>
              </div>
            ) : (
              /* Handle Real Data */
              <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-6">
                {properties.map((listing) => (
                  <div key={listing.id} className="group bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-lg hover:border-gray-300 transition-all duration-300 flex flex-col cursor-pointer">
                    
                    {/* Image Container */}
                    <div className="relative h-48 overflow-hidden bg-gray-100">
                      <img 
                        src={listing.image_url || "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?q=80&w=800&auto=format&fit=crop"} 
                        alt={listing.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      />
                      {/* Optional NLP Badge */}
                      {listing.nlp_sentiment && (
                        <div className="absolute top-3 left-3">
                          <span className={`px-2.5 py-1 text-[11px] uppercase tracking-wider font-bold rounded-md shadow-sm ${
                            listing.nlp_sentiment === 'Mostly Positive' ? 'bg-[#1D9E75] text-white' : 'bg-[#C55A11] text-white'
                          }`}>
                            {listing.nlp_sentiment}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Card Body */}
                    <div className="p-5 flex flex-col flex-1">
                      <div className="flex justify-between items-start mb-1.5">
                        <h3 className="font-bold text-gray-900 line-clamp-1">{listing.title}</h3>
                        <div className="flex items-center gap-1 bg-amber-50 px-1.5 py-0.5 rounded text-amber-700">
                          <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                          <span className="text-xs font-bold">{listing.average_rating || "New"}</span>
                        </div>
                      </div>
                      
                      <p className="text-gray-500 text-xs flex items-center gap-1 mb-4">
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{listing.address}</span>
                      </p>
                      
                      <div className="mt-auto pt-4 border-t border-gray-100 flex items-center justify-between">
                        <div>
                          <span className="text-xl font-black text-[#1F4E79]">R {listing.price?.toLocaleString("en-ZA") || "0"}</span>
                          <span className="text-gray-500 text-xs font-medium"> / mo</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination Mockup */}
            {!loading && properties.length > 0 && (
              <div className="mt-12 text-center">
                <Button variant="outline" className="rounded-full px-8 font-semibold text-gray-600 hover:text-gray-900 border-gray-300">
                  Load more properties
                </Button>
              </div>
            )}
          </main>

        </div>
      </div>
    </div>
  );
}