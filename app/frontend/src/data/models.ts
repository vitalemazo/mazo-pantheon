import { api } from '@/services/api';

export interface LanguageModel {
  display_name: string;
  model_name: string;
  provider: string;
}

// Cache for models to avoid repeated API calls
let languageModels: LanguageModel[] | null = null;

/**
 * Get the list of models from the backend API
 * Uses caching to avoid repeated API calls
 */
export const getModels = async (forceRefresh = false): Promise<LanguageModel[]> => {
  if (languageModels && languageModels.length > 0 && !forceRefresh) {
    return languageModels;
  }

  try {
    const models = await api.getLanguageModels();
    if (models && models.length > 0) {
      languageModels = models;
    }
    return languageModels || [];
  } catch (error) {
    console.error('Failed to fetch models:', error);
    return []; // Return empty array instead of throwing to prevent UI crashes
  }
};

/**
 * Get the default model (GPT-4.1) from the models list
 */
export const getDefaultModel = async (): Promise<LanguageModel | null> => {
  try {
    const models = await getModels();
    return models.find(model => model.model_name === "gpt-4.1") || models[0] || null;
  } catch (error) {
    console.error('Failed to get default model:', error);
    return null;
  }
};
