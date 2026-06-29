import { BotProfile, BotSkill } from '@/services/api';
import { BotCenterLoaders } from './useBotCenterLoaders';
import { BotCenterState } from './useBotCenterState';

export type BotCenterOption = { value: string; label: string };

export type BotCenterDerived = {
  selectedProfileData?: BotProfile;
  boundSkills: BotSkill[];
  profileOptions: BotCenterOption[];
  skillOptions: BotCenterOption[];
  bindingOptions: BotCenterOption[];
};

export type BotCenterActionContext = BotCenterState & BotCenterLoaders & BotCenterDerived;
