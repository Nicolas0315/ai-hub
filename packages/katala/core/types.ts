export interface IdentityVector {
  personality: {
    extraversion: number;
    intuition: number;
    thinking: number;
    judging: number;
  };
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
