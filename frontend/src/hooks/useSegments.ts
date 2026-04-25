"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import type { Segment, SegmentsResponse } from "@/lib/review-types";

export function useSegments(jobId: string) {
  return useQuery<Segment[]>({
    queryKey: ["segments", jobId],
    queryFn: async () => {
      const res = await fetch(`/api/jobs/${jobId}/segments`);
      if (!res.ok) throw new Error("Failed to load segments");
      const data: SegmentsResponse = await res.json();
      return data.segments;
    },
    enabled: !!jobId,
  });
}

export function useSegmentPatch(jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: async ({
      segmentId,
      editedText,
    }: {
      segmentId: string;
      editedText: string | null;
    }) => {
      const res = await fetch(`/api/jobs/${jobId}/segments/${segmentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edited_text: editedText }),
      });
      if (!res.ok) throw new Error("Save failed");
      return res.json() as Promise<Segment>;
    },

    onMutate: async ({ segmentId, editedText }) => {
      await queryClient.cancelQueries({ queryKey: ["segments", jobId] });
      const previousSegments = queryClient.getQueryData<Segment[]>([
        "segments",
        jobId,
      ]);
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) =>
          seg.id === segmentId ? { ...seg, edited_text: editedText } : seg
        ) ?? []
      );
      return { previousSegments };
    },

    onError: (_err, _vars, context) => {
      if (context?.previousSegments) {
        queryClient.setQueryData(
          ["segments", jobId],
          context.previousSegments
        );
      }
      toast({
        title: "Could not save — edit restored.",
        variant: "destructive",
      });
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] });
    },
  });
}

export function useSegmentRegenerate(jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: async (segmentId: string) => {
      const res = await fetch(`/api/jobs/${jobId}/segments/${segmentId}/regenerate`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Regenerate failed");
      return res.json() as Promise<{ translated_text: string }>;
    },
    onSuccess: (data, segmentId) => {
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) =>
          seg.id === segmentId
            ? { ...seg, translated_text: data.translated_text }
            : seg
        ) ?? []
      );
    },
    onError: () => {
      toast({
        title: "Regeneration failed. Try again.",
        variant: "destructive",
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] });
    },
  });
}
