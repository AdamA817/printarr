import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { familiesApi } from '@/services/api'
import type {
  FamilyListParams,
  CreateFamilyRequest,
  UpdateFamilyRequest,
  GroupDesignsRequest,
} from '@/types/family'

/**
 * Hook to fetch paginated list of families
 */
export function useFamilies(params?: FamilyListParams) {
  return useQuery({
    queryKey: ['families', params],
    queryFn: () => familiesApi.list(params),
    staleTime: 30000, // 30 seconds
  })
}

/**
 * Hook to fetch a single family with its variants
 */
export function useFamily(id: string | undefined) {
  return useQuery({
    queryKey: ['family', id],
    queryFn: () => familiesApi.get(id!),
    enabled: !!id,
    staleTime: 30000,
  })
}

/**
 * Hook to create a new family
 */
export function useCreateFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateFamilyRequest) => familiesApi.create(data),
    onSuccess: () => {
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
    },
  })
}

/**
 * Hook to update a family's metadata
 */
export function useUpdateFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateFamilyRequest }) =>
      familiesApi.update(id, data),
    onSuccess: (family) => {
      // Update the family in cache
      queryClient.setQueryData(['family', family.id], family)
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
    },
  })
}

/**
 * Hook to delete a family (orphans its designs)
 */
export function useDeleteFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => familiesApi.delete(id),
    onSuccess: (_, id) => {
      // Remove family from cache
      queryClient.removeQueries({ queryKey: ['family', id] })
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs as they may have been updated
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to group designs into a new or existing family
 */
export function useGroupDesigns() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: GroupDesignsRequest) => familiesApi.groupDesigns(data),
    onSuccess: (family) => {
      // Update or add family to cache
      queryClient.setQueryData(['family', family.id], family)
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs as they've been updated
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to remove a design from a family
 */
export function useUngroupDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ familyId, designId }: { familyId: string; designId: string }) =>
      familiesApi.ungroupDesign(familyId, { design_id: designId }),
    onSuccess: (_, { familyId }) => {
      // Invalidate the family
      queryClient.invalidateQueries({ queryKey: ['family', familyId] })
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to dissolve a family (remove all designs from it)
 */
export function useDissolveFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => familiesApi.dissolve(id),
    onSuccess: (_, id) => {
      // Remove family from cache
      queryClient.removeQueries({ queryKey: ['family', id] })
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to run auto-detection on all designs without families
 */
export function useRunFamilyDetection() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => familiesApi.runDetection(),
    onSuccess: () => {
      // Invalidate both families and designs
      queryClient.invalidateQueries({ queryKey: ['families'] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to detect family for a specific design
 */
export function useDetectFamilyForDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (designId: string) => familiesApi.detectForDesign(designId),
    onSuccess: (result) => {
      // If a family was found/created, invalidate related queries
      if (result.family_id) {
        queryClient.invalidateQueries({ queryKey: ['family', result.family_id] })
        queryClient.invalidateQueries({ queryKey: ['families'] })
      }
      // Always invalidate designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to add a design to an existing family
 */
export function useAddDesignToFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      familyId,
      designId,
      variantName,
    }: {
      familyId: string
      designId: string
      variantName?: string
    }) => familiesApi.addDesign(familyId, designId, variantName),
    onSuccess: (_, { familyId }) => {
      // Invalidate the family
      queryClient.invalidateQueries({ queryKey: ['family', familyId] })
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Hook to remove a design from a family
 */
export function useRemoveDesignFromFamily() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ familyId, designId }: { familyId: string; designId: string }) =>
      familiesApi.removeDesign(familyId, designId),
    onSuccess: (_, { familyId }) => {
      // Invalidate the family
      queryClient.invalidateQueries({ queryKey: ['family', familyId] })
      // Invalidate families list
      queryClient.invalidateQueries({ queryKey: ['families'] })
      // Invalidate designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}
