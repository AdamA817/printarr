// Must match backend/app/db/models/enums.py FamilyDetectionMethod
export type FamilyDetectionMethod = 'NAME_PATTERN' | 'FILE_HASH_OVERLAP' | 'AI_DETECTED' | 'MANUAL'

// Must match backend/app/api/routes/families.py DesignSummaryResponse
export interface FamilyDesignSummary {
  id: string
  canonical_title: string
  canonical_designer: string
  variant_name: string | null
  status: string
}

// Must match backend/app/api/routes/families.py FamilyTagResponse
export interface FamilyTag {
  id: string
  name: string
  category: string | null
  is_predefined: boolean
  source: string
  assigned_at: string | null
}

// Must match backend/app/api/routes/families.py FamilyResponse
export interface Family {
  id: string
  canonical_name: string
  canonical_designer: string
  name_override: string | null
  designer_override: string | null
  description: string | null
  detection_method: FamilyDetectionMethod
  detection_confidence: number | null
  display_name: string
  display_designer: string
  variant_count: number
  created_at: string
  updated_at: string
}

// Must match backend/app/api/routes/families.py FamilyDetailResponse
export interface FamilyDetail extends Family {
  designs: FamilyDesignSummary[]
  tags: FamilyTag[]
}

// Must match backend/app/api/routes/families.py FamilyListResponse
export interface FamilyList {
  items: Family[]
  total: number
  page: number
  limit: number
}

// Must match backend/app/api/routes/families.py CreateFamilyRequest
export interface CreateFamilyRequest {
  name: string
  designer?: string
  description?: string | null
}

// Must match backend/app/api/routes/families.py UpdateFamilyRequest
export interface UpdateFamilyRequest {
  name_override?: string | null
  designer_override?: string | null
  description?: string | null
}

// Must match backend/app/api/routes/families.py GroupDesignsRequest
export interface GroupDesignsRequest {
  design_ids: string[]
  family_name?: string | null
  family_id?: string | null
}

// Must match backend/app/api/routes/families.py UngroupDesignRequest
export interface UngroupDesignRequest {
  design_id: string
}

// Must match backend/app/api/routes/families.py DetectionResultResponse
export interface DetectionResultResponse {
  families_created: number
  designs_grouped: number
  families_updated: number
}

// Query params for listing families
export interface FamilyListParams {
  page?: number
  limit?: number
  designer?: string
}

// Response for adding design to family
export interface AddDesignToFamilyResponse {
  message: string
  design_id: string
  family_id: string
  variant_name: string | null
}

// Response for removing design from family
export interface RemoveDesignFromFamilyResponse {
  message: string
}

// Response for dissolving family
export interface DissolveFamilyResponse {
  message: string
  designs_removed: number
}

// Response for detecting family for a specific design
export interface DetectFamilyForDesignResponse {
  message: string
  family_id: string | null
  family_name?: string
  variants_found?: number
}
