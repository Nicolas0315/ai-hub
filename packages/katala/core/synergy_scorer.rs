use std::collections::HashMap;

pub struct PhoenixScores {
    pub favorite_score: Option<f64>,
    pub reply_score: Option<f64>,
    pub retweet_score: Option<f64>,
    pub photo_expand_score: Option<f64>,
    pub click_score: Option<f64>,
    pub profile_click_score: Option<f64>,
    pub vqv_score: Option<f64>,
    pub share_score: Option<f64>,
    pub share_via_dm_score: Option<f64>,
    pub share_via_copy_link_score: Option<f64>,
    pub dwell_score: Option<f64>,
    pub quote_score: Option<f64>,
    pub quoted_click_score: Option<f64>,
    pub dwell_time: Option<f64>,
    pub follow_author_score: Option<f64>,
    pub not_interested_score: Option<f64>,
    pub block_author_score: Option<f64>,
    pub mute_author_score: Option<f64>,
    pub report_score: Option<f64>,
}

pub struct ScoringWeights {
    pub favorite_weight: f64,
    pub reply_weight: f64,
    pub retweet_weight: f64,
    pub photo_expand_weight: f64,
    pub click_weight: f64,
    pub profile_click_weight: f64,
    pub vqv_weight: f64,
    pub share_weight: f64,
    pub share_via_dm_weight: f64,
    pub share_via_copy_link_weight: f64,
    pub dwell_weight: f64,
    pub quote_weight: f64,
    pub quoted_click_weight: f64,
    pub cont_dwell_time_weight: f64,
    pub follow_author_weight: f64,
    pub not_interested_weight: f64,
    pub block_author_weight: f64,
    pub mute_author_weight: f64,
    pub report_weight: f64,
}

impl Default for ScoringWeights {
    fn default() -> Self {
        Self {
            favorite_weight: 0.5,
            reply_weight: 1.0,
            retweet_weight: 0.8,
            photo_expand_weight: 0.2,
            click_weight: 0.3,
            profile_click_weight: 0.4,
            vqv_weight: 0.6,
            share_weight: 0.7,
            share_via_dm_weight: 1.2,
            share_via_copy_link_weight: 0.9,
            dwell_weight: 0.1,
            quote_weight: 1.1,
            quoted_click_weight: 0.5,
            cont_dwell_time_weight: 0.01,
            follow_author_weight: 2.0,
            not_interested_weight: -1.0,
            block_author_weight: -5.0,
            mute_author_weight: -3.0,
            report_weight: -10.0,
        }
    }
}

pub struct SynergyScorer {
    weights: ScoringWeights,
}

impl SynergyScorer {
    pub fn new(weights: Option<ScoringWeights>) -> Self {
        Self {
            weights: weights.unwrap_or_default(),
        }
    }

    fn apply_weight(&self, score: Option<f64>, weight: f64) -> f64 {
        score.unwrap_or(0.0) * weight
    }

    pub fn compute_weighted_score(&self, scores: &PhoenixScores) -> f64 {
        let mut combined_score = 0.0;

        combined_score += self.apply_weight(scores.favorite_score, self.weights.favorite_weight);
        combined_score += self.apply_weight(scores.reply_score, self.weights.reply_weight);
        combined_score += self.apply_weight(scores.retweet_score, self.weights.retweet_weight);
        combined_score += self.apply_weight(scores.photo_expand_score, self.weights.photo_expand_weight);
        combined_score += self.apply_weight(scores.click_score, self.weights.click_weight);
        combined_score += self.apply_weight(scores.profile_click_score, self.weights.profile_click_weight);
        combined_score += self.apply_weight(scores.vqv_score, self.weights.vqv_weight);
        combined_score += self.apply_weight(scores.share_score, self.weights.share_weight);
        combined_score += self.apply_weight(scores.share_via_dm_score, self.weights.share_via_dm_weight);
        combined_score += self.apply_weight(scores.share_via_copy_link_score, self.weights.share_via_copy_link_weight);
        combined_score += self.apply_weight(scores.dwell_score, self.weights.dwell_weight);
        combined_score += self.apply_weight(scores.quote_score, self.weights.quote_weight);
        combined_score += self.apply_weight(scores.quoted_click_score, self.weights.quoted_click_weight);
        combined_score += self.apply_weight(scores.dwell_time, self.weights.cont_dwell_time_weight);
        combined_score += self.apply_weight(scores.follow_author_score, self.weights.follow_author_weight);
        combined_score += self.apply_weight(scores.not_interested_score, self.weights.not_interested_weight);
        combined_score += self.apply_weight(scores.block_author_score, self.weights.block_author_weight);
        combined_score += self.apply_weight(scores.mute_author_score, self.weights.mute_author_weight);
        combined_score += self.apply_weight(scores.report_score, self.weights.report_weight);

        combined_score
    }

    pub fn compute_synergy(&self, interests_a: &HashMap<String, f64>, interests_b: &HashMap<String, f64>) -> f64 {
        let mut synergy = 0.0;
        for (category, weight_a) in interests_a {
            if let Some(weight_b) = interests_b.get(category) {
                synergy += weight_a * weight_b;
            }
        }
        synergy
    }
}
