import { useState } from 'react';
import { Sparkles, Info, Plus, X, ShieldCheck, Check } from 'lucide-react';
import { RecommendationItem } from '../types.ts';

interface RecommendationCardProps {
  recommendation: RecommendationItem;
  onAccept: (rec: RecommendationItem) => void;
  onDismiss: (productId: string) => void;
  onOpenPassport?: (rec: RecommendationItem) => void;
  isAdded?: boolean;
  explanationText?: string;
  factualSignals?: string[];
  isAiGenerated?: boolean;
}

export function RecommendationCard({
  recommendation,
  onAccept,
  onDismiss,
  onOpenPassport,
  isAdded = false,
  explanationText,
  factualSignals,
  isAiGenerated = false,
}: RecommendationCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const hasOffer = recommendation.is_offered;
  const discountPct = Math.round(recommendation.discount_percentage * 100);
  const savings = recommendation.savings;
  const finalPrice = recommendation.final_price;

  // Use natural explanation if available, fallback to deterministic attribute reason
  const displayedExplanation = explanationText || recommendation.compatibility_reason;

  return (
    <div className={`relative rounded-xl border p-4 shadow-sm transition-all flex flex-col justify-between ${
      hasOffer
        ? 'border-indigo-200 bg-gradient-to-b from-indigo-50/50 to-white hover:border-indigo-300'
        : 'border-slate-200 bg-white hover:border-slate-300'
    }`}>
      <div>
        {/* Top Header Badge */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Sparkles className={`w-3.5 h-3.5 ${hasOffer ? 'text-indigo-600' : 'text-slate-500'}`} />
            <span className={`text-[11px] font-bold uppercase tracking-wider ${
              hasOffer ? 'text-indigo-700' : 'text-slate-600'
            }`}>
              {hasOffer ? 'Eligible Bundle Deal' : 'Compatible Accessory'}
            </span>
            {isAiGenerated && (
              <span className="text-[9px] bg-indigo-100 text-indigo-800 font-semibold px-1.5 py-0.2 rounded border border-indigo-200">
                ✨ AI Copy
              </span>
            )}
            {recommendation.is_multi_item_match && (
              <span className="text-[9px] bg-purple-100 text-purple-800 font-semibold px-1.5 py-0.5 rounded border border-purple-200">
                ✨ Multi-Item Match
              </span>
            )}
            {recommendation.association_lift !== undefined && recommendation.association_lift > 1.2 && (
              <span
                className="text-[9px] bg-blue-100 text-blue-800 font-semibold px-1.5 py-0.5 rounded border border-blue-200"
                title={`Association lift: ${recommendation.association_lift.toFixed(1)}x (${Math.round((recommendation.association_confidence ?? 0) * 100)}% confidence)`}
              >
                📈 {recommendation.association_lift.toFixed(1)}x Lift
              </span>
            )}
          </div>

          <button
            onClick={() => onDismiss(recommendation.product_id)}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors"
            title="Dismiss recommendation"
            aria-label="Dismiss recommendation"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Provenance Anchor Pill */}
        {recommendation.provenance_label && (
          <div className="mb-2">
            <span className="inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
              🧭 {recommendation.provenance_label}
            </span>
          </div>
        )}

        {/* Product Info & Thumbnail */}
        <div className="flex items-start space-x-3">
          <img
            src={recommendation.image_url}
            alt={recommendation.name}
            className="w-16 h-16 rounded-lg object-cover bg-slate-100 border border-slate-200 shrink-0"
            onError={(e) => {
              e.currentTarget.src =
                'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
            }}
          />

          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                {recommendation.category}
              </span>
              {recommendation.subcategory && recommendation.subcategory !== recommendation.category && (
                <>
                  <span className="text-[10px] text-slate-300">·</span>
                  <span className="text-[10px] text-slate-400 font-medium">
                    {recommendation.subcategory}
                  </span>
                </>
              )}
            </div>

            <h4 className="text-xs font-bold text-slate-900 leading-snug line-clamp-1 mt-0.5">
              {recommendation.name}
            </h4>

            <p className="text-[11px] text-slate-600 mt-1 leading-relaxed line-clamp-2">
              {displayedExplanation}
            </p>

            {/* Pricing Row */}
            <div className="mt-2.5 flex items-baseline flex-wrap gap-2">
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
                    {recommendation.conditions || 'Standard price · Add items to cart to unlock bundle deals'}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3">
        {/* Conditions & Disclosure Toggle */}
        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] gap-2">
          <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="inline-flex items-center space-x-1 text-slate-500 hover:text-indigo-600 transition-colors"
            >
              <Info className="w-3 h-3" />
              <span>{showDetails ? 'Hide' : 'Why item?'}</span>
            </button>

            {onOpenPassport && (
              <button
                onClick={() => onOpenPassport(recommendation)}
                className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold border border-indigo-200 transition-colors cursor-pointer"
                title="Open Fair Deal Passport counterfactual audit"
              >
                <Sparkles className="w-3 h-3 text-indigo-600" />
                <span>Deal Passport</span>
              </button>
            )}
          </div>

          {hasOffer && (
            <span className="text-[10px] text-indigo-700 font-medium truncate max-w-[150px]">
              {recommendation.conditions}
            </span>
          )}
        </div>

        {/* Expandable Transparency Details */}
        {showDetails && (
          <div className="mt-2 p-2.5 bg-slate-50 rounded-lg text-[11px] text-slate-600 space-y-1.5 border border-slate-200">
            <div className="flex items-center space-x-1 text-indigo-900 font-semibold">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
              <span>FairCart AI Transparency Disclosure</span>
            </div>
            <p className="leading-relaxed">
              <strong>Relevance Score:</strong> {Math.round(recommendation.affinity_score * 100)}% affinity based on compatibility attributes.
            </p>
            {recommendation.is_multi_item_match && (
              <p className="leading-relaxed text-purple-700">
                <strong>Basket Synergy:</strong> Directly complements multiple items currently in your basket.
              </p>
            )}
            {recommendation.association_lift !== undefined && recommendation.association_lift > 1.0 && (
              <p className="leading-relaxed text-blue-700">
                <strong>Basket Association:</strong> {recommendation.association_lift.toFixed(2)}x co-occurrence lift ({Math.round((recommendation.association_confidence ?? 0) * 100)}% confidence in synthetic basket transactions).
              </p>
            )}
            {factualSignals && factualSignals.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-0.5">
                {factualSignals.map((sig, i) => (
                  <span key={i} className="text-[9px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded font-mono">
                    {sig}
                  </span>
                ))}
              </div>
            )}
            <p className="leading-relaxed">
              <strong>Economic Rule:</strong>{' '}
              {hasOffer
                ? `A ${discountPct}% incentive was approved because combined basket gross margin (${(recommendation.basket_gross_margin * 100).toFixed(1)}%) satisfies the merchant floor.`
                : 'Offered at standard reference price because applying a discount would breach the merchant gross margin floor.'}
            </p>
          </div>
        )}

        {/* Action Button */}
        <div className="mt-2.5">
          {isAdded ? (
            <div className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span>Added to Cart</span>
            </div>
          ) : (
            <button
              onClick={() => onAccept(recommendation)}
              className={`w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg text-white text-xs font-semibold shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 ${
                hasOffer
                  ? 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500'
                  : 'bg-slate-900 hover:bg-slate-800 focus:ring-slate-900'
              }`}
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
    </div>
  );
}
