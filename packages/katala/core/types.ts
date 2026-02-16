export interface MBTIPlusPlus {
  // 16 Identity Dimensions
  // Energy (Extraversion - Introversion)
  extraversion_introversion: number;
  // Information (Sensing - Intuition)
  sensing_intuition: number;
  // Decision (Thinking - Feeling)
  thinking_feeling: number;
  // Execution (Judging - Perceiving)
  judging_perceiving: number;
  // Orientation (Assertive - Turbulent)
  assertive_turbulent: number;
  // Cognition (Systematic - Adaptive)
  systematic_adaptive: number;
  // Communication (Direct - Diplomatic)
  direct_diplomatic: number;
  // Value (Individualism - Collectivism)
  individualism_collectivism: number;
  // Learning (Practical - Theoretical)
  practical_theoretical: number;
  // Tempo (Fast - Deliberate)
  fast_deliberate: number;
  // Risk (Cautious - Bold)
  cautious_bold: number;
  // Scope (Micro - Macro)
  micro_macro: number;
  // Source (Internal - External)
  internal_external: number;
  // Focus (Task - People)
  task_people: number;
  // Response (Proactive - Reactive)
  proactive_reactive: number;
  // Mode (Specialist - Generalist)
  mode_specialist_generalist: number;
}

export interface IdentityVector {
  personality: MBTIPlusPlus;
  values: string[];
  professionalFocus: string[];
  socialEnergy: {
    battery: number;
    preferredTone: "concise" | "enthusiastic" | "professional" | "casual";
  };
  meta: {
    confidenceScore: number;
    lastUpdated: string;
  };
}
