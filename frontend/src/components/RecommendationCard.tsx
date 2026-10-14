import { useState } from 'react';
import { Sparkles, Info, Plus, X, ShieldCheck, Check } from 'lucide-react';
import { RecommendationResponse, IncentiveResponse } from '../types.ts';

interface RecommendationCardProps {
  recommendation: RecommendationResponse;
  incentive: IncentiveResponse | null;
  onAccept: (rec: RecommendationResponse, incentive: IncentiveResponse | null) => void;
  onDismiss: () => void;
  isAdded?: boolean;
}

export function RecommendationCard({
  recommendation,
  incentive,
  onAccept,
  onDismiss,
  isAdded = false,
}: RecommendationCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const hasOffer = incentive?.is_offered ?? false;
  const discountPct = incentive ? Math.round(incentive.discount_percentage * 100) : 0;
  const savings = incentive?.savings ?? 0;
  const finalPrice = incentive?.final_price ?? recommendation.reference_price;

  return (
    <div className="relative rounded-xl border border-indigo-100 bg-gradient-to-b from-indigo-50/40 to-white p-3.5 shadow-sm transition-all hover:border-indigo-200">
      {/* Top Header Badge */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center space-x-1.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700">
            {hasOffer ? 'Recommended Bundle Deal' : 'Compatible Accessory'}
          </span>
        </div>

        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors"
          title="Dismiss recommendation"
          aria-label="Dismiss recommendation"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Main Product Info & Image */}
      <div className="flex items-start space-x-3">
        <img
          src={recommendation.image_url}
          alt={recommendation.name}
          className="w-14 h-14 rounded-lg object-cover bg-slate-100 border border-slate-200 shrink-0"
          onError={(e) => {
            e.currentTarget.src =
              'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
          }}
        />

        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-slate-900 leading-snug line-clamp-1">
            {recommendation.name}
          </h4>
          <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed line-clamp-2">
            {recommendation.compatibility_reason}
          </p>

          {/* Pricing & Offer Badge Row */}
          <div className="mt-2 flex items-baseline flex-wrap gap-2">
            {hasOffer ? (
              <>
                <span className="text-sm font-bold text-slate-900 font-mono">
                  ${finalPrice.toFixed(2)}
                </span>
                <span className="text-xs text-slate-400 line-through font-mono">
                  ${recommendation.reference_price.toFixed(2)}
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                  Save ${savings.toFixed(2)} ({discountPct}% OFF)
                </span>
              </>
            ) : (
              <>
                <span className="text-sm font-bold text-slate-900 font-mono">
                  ${recommendation.reference_price.toFixed(2)}
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                  Standard price · No discount applied
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Transparent Explanation Toggle */}
      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="inline-flex items-center space-x-1 text-slate-500 hover:text-indigo-600 transition-colors"
        >
          <Info className="w-3 h-3" />
          <span>{showDetails ? 'Hide offer details' : 'Why this item?'}</span>
        </button>

        {hasOffer && (
          <span className="text-[10px] text-slate-400 font-medium truncate max-w-[170px]">
            {incentive?.conditions}
          </span>
        )}
      </div>

      {/* Expandable Explanation Details */}
      {showDetails && (
        <div className="mt-2 p-2.5 bg-slate-50 rounded-lg text-[11px] text-slate-600 space-y-1.5 border border-slate-200">
          <div className="flex items-center space-x-1 text-indigo-900 font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
            <span>FairCart AI Transparency Disclosure</span>
          </div>
          <p className="leading-relaxed">
            <strong>Relevance:</strong> {recommendation.compatibility_reason} (Compatibility affinity:{' '}
            {Math.round(recommendation.affinity_score * 100)}%)
          </p>
          <p className="leading-relaxed">
            <strong>Economics:</strong>{' '}
            {hasOffer
              ? `A ${discountPct}% incentive was approved because total basket gross margin satisfies the merchant's 20% floor.`
              : 'Offered at full reference price because discounting would breach the merchant gross margin floor.'}
          </p>
        </div>
      )}

      {/* Action CTA */}
      <div className="mt-2.5">
        {isAdded ? (
          <div className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
            <Check className="w-3.5 h-3.5 text-emerald-600" />
            <span>Added to Cart</span>
          </div>
        ) : (
          <button
            onClick={() => onAccept(recommendation, incentive)}
            className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>
              {hasOffer
                ? `Add Bundle for $${finalPrice.toFixed(2)}`
                : `Add Accessory ($${recommendation.reference_price.toFixed(2)})`}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
