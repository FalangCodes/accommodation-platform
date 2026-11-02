/** Public fields returned by the accommodation insights endpoint. */
export interface AspectInsight {
  display_name: string;
  mention_count: number;
  positive_rate: number;
  negative_rate: number;
  overall_sentiment: string;
  student_sentiment: string;
  sentiment_label: string;
  show_to_students: boolean;
  star_rating: number;
  overall_opinion: string;
  strengths?: string[];
  concerns?: string[];
  summary_generated_at?: string | null;
  summary_review_count?: number;
}

export interface AccommodationInsights {
  insights: Record<string, AspectInsight>;
  review_count: number;
  recommendations?: {
    aspect: string;
    display_name: string;
    priority: string;
    recommendation: string;
    positive_rate: number;
    mention_count: number;
    summary_generated_at?: string | null;
    summary_review_count?: number;
  }[];
}
