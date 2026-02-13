'use client';

import { useState } from 'react';

interface FeedbackFormProps {
  mediationScore: number;
  onClose: () => void;
}

export default function FeedbackForm({ mediationScore, onClose }: FeedbackFormProps) {
  const [rating, setRating] = useState<number>(0);
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (rating === 0) {
      alert('評価を選択してください');
      return;
    }

    setIsSubmitting(true);
    setSubmitStatus('idle');

    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mediationScore,
          userRating: rating,
          comment,
          timestamp: new Date().toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      setSubmitStatus('success');

      // Close form after 2 seconds
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (error) {
      console.error('Error submitting feedback:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-3xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-semibold">フィードバック</h3>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-2xl leading-none"
          aria-label="閉じる"
        >
          ×
        </button>
      </div>

      {submitStatus === 'success' ? (
        <div className="text-center py-8">
          <div className="text-5xl mb-4">✓</div>
          <p className="text-lg font-medium text-green-600 dark:text-green-400">
            フィードバックを送信しました
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
            ご協力ありがとうございます
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Rating */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              この仲介結果をどう評価しますか？
            </label>
            <div className="flex justify-center space-x-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setRating(value)}
                  className={`w-12 h-12 rounded-full transition-all ${
                    rating >= value
                      ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white scale-110'
                      : 'bg-gray-200 dark:bg-zinc-800 text-gray-400 dark:text-gray-600 hover:bg-gray-300 dark:hover:bg-zinc-700'
                  }`}
                >
                  ★
                </button>
              ))}
            </div>
            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-2 px-2">
              <span>不正確</span>
              <span>正確</span>
            </div>
          </div>

          {/* Comment */}
          <div>
            <label
              htmlFor="comment"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              コメント（任意）
            </label>
            <textarea
              id="comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={4}
              placeholder="この結果についてのご意見をお聞かせください..."
              className="w-full px-4 py-3 rounded-2xl border border-gray-300 dark:border-neutral-700 bg-white dark:bg-zinc-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
            />
          </div>

          {/* Error Message */}
          {submitStatus === 'error' && (
            <div className="text-sm text-red-600 dark:text-red-400 text-center">
              送信に失敗しました。もう一度お試しください。
            </div>
          )}

          {/* Submit Button */}
          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2 rounded-full bg-gray-200 dark:bg-zinc-800 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-300 dark:hover:bg-zinc-700 transition-all"
            >
              キャンセル
            </button>
            <button
              type="submit"
              disabled={isSubmitting || rating === 0}
              className="px-6 py-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 text-white font-medium hover:from-blue-600 hover:to-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? '送信中...' : '送信'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
