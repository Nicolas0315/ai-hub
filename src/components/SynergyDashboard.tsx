'use client';

import { useState, useEffect } from 'react';
import { KaniMediationResponse } from '@/lib/kani/types';
import { IdentityDimensions } from '@/lib/synergy/engine';
import FeedbackForm from './FeedbackForm';

interface SynergyDashboardProps {
  identityA: IdentityDimensions;
  identityB: IdentityDimensions;
  mediationResult?: KaniMediationResponse;
}

export default function SynergyDashboard({
  identityA,
  identityB,
  mediationResult,
}: SynergyDashboardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<KaniMediationResponse | undefined>(mediationResult);
  const [showFeedback, setShowFeedback] = useState(false);

  const calculateMediation = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/kani', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          identityA,
          identityB,
          xParams: {
            dwellTimeSeconds: 45,
            shareVelocity: 0.7,
            reciprocalInteraction: false,
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to calculate mediation');
      }

      const data = await response.json();
      setResult(data);
      setShowFeedback(true);
    } catch (error) {
      console.error('Error calculating mediation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-blue-600 dark:text-blue-400';
    if (score >= 40) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 80) return '優秀';
    if (score >= 60) return '良好';
    if (score >= 40) return '普通';
    return '要改善';
  };

  return (
    <div className="w-full max-w-5xl space-y-6">
      {/* Header */}
      <div className="rounded-3xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-2">シナジー分析</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          2つのアイデンティティプロファイル間の相性を評価
        </p>
      </div>

      {/* Identity Profiles */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <IdentityCard title="アイデンティティ A" identity={identityA} />
        <IdentityCard title="アイデンティティ B" identity={identityB} />
      </div>

      {/* Calculation Button */}
      {!result && (
        <div className="flex justify-center">
          <button
            onClick={calculateMediation}
            disabled={isLoading}
            className="px-8 py-3 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold hover:from-blue-600 hover:to-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
          >
            {isLoading ? 'シナジー計算中...' : 'シナジースコアを計算'}
          </button>
        </div>
      )}

      {/* Mediation Result */}
      {result && (
        <>
          <div className="rounded-3xl border border-gray-200 dark:border-neutral-800 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-zinc-900/80 dark:to-zinc-900/80 backdrop-blur-sm shadow-lg p-8">
            <div className="text-center space-y-4">
              <h3 className="text-xl font-semibold text-gray-700 dark:text-gray-300">
                仲介スコア
              </h3>
              <div className={`text-6xl font-bold ${getScoreColor(result.mediationScore)}`}>
                {result.mediationScore.toFixed(1)}
              </div>
              <div className={`text-lg font-medium ${getScoreColor(result.mediationScore)}`}>
                {getScoreLabel(result.mediationScore)}
              </div>

              {result.synergyScore !== undefined && (
                <div className="mt-6 pt-6 border-t border-gray-200 dark:border-neutral-700">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    シナジースコア
                  </div>
                  <div className="text-3xl font-semibold text-purple-600 dark:text-purple-400">
                    {result.synergyScore.toFixed(1)}
                  </div>
                </div>
              )}

              {result.recommendations && result.recommendations.length > 0 && (
                <div className="mt-6 pt-6 border-t border-gray-200 dark:border-neutral-700 text-left">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                    推奨事項
                  </h4>
                  <ul className="space-y-2">
                    {result.recommendations.map((rec, idx) => (
                      <li key={idx} className="text-sm text-gray-600 dark:text-gray-400 flex items-start">
                        <span className="mr-2">•</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Feedback Form */}
          {showFeedback && (
            <FeedbackForm
              mediationScore={result.mediationScore}
              onClose={() => setShowFeedback(false)}
            />
          )}

          {/* Recalculate Button */}
          <div className="flex justify-center">
            <button
              onClick={calculateMediation}
              disabled={isLoading}
              className="px-6 py-2 rounded-full bg-gray-200 dark:bg-zinc-800 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-300 dark:hover:bg-zinc-700 transition-all disabled:opacity-50"
            >
              再計算
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function IdentityCard({ title, identity }: { title: string; identity: IdentityDimensions }) {
  const dimensions = [
    { key: 'IE', label: '内向 ↔ 外向', value: identity.IE },
    { key: 'SN', label: '感覚 ↔ 直感', value: identity.SN },
    { key: 'TF', label: '思考 ↔ 感情', value: identity.TF },
    { key: 'JP', label: '判断 ↔ 知覚', value: identity.JP },
    { key: 'Openness', label: '開放性', value: identity.Openness },
    { key: 'Conscientiousness', label: '誠実性', value: identity.Conscientiousness },
    { key: 'Agreeableness', label: '協調性', value: identity.Agreeableness },
    { key: 'Empathy', label: '共感力', value: identity.Empathy },
  ];

  return (
    <div className="rounded-3xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm p-6">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="space-y-3">
        {dimensions.map((dim) => (
          <div key={dim.key} className="space-y-1">
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-600 dark:text-gray-400">{dim.label}</span>
              <span className="font-medium">{dim.value.toFixed(2)}</span>
            </div>
            <div className="h-2 bg-gray-200 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-300"
                style={{ width: `${((dim.value + 1) / 2) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
