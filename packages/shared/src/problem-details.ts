import { z } from "zod";

const ProblemCodeSchema = z.string().regex(/^[a-z][a-z0-9_]*$/);

export const ApiFieldErrorSchema = z.strictObject({
  /** JSON Pointer to the invalid request member; an empty string addresses the document. */
  pointer: z.string().regex(/^(?:$|\/)/),
  code: ProblemCodeSchema,
  message: z.string().trim().min(1),
});
export type ApiFieldError = z.infer<typeof ApiFieldErrorSchema>;

/** RFC 9457 problem details plus stable machine codes and field errors. */
export const ApiProblemSchema = z.strictObject({
  type: z.string().trim().min(1).default("about:blank"),
  title: z.string().trim().min(1),
  status: z.number().int().min(400).max(599),
  detail: z.string().trim().min(1).optional(),
  instance: z.string().trim().min(1).optional(),
  code: ProblemCodeSchema,
  errors: z.array(ApiFieldErrorSchema).optional(),
});
export type ApiProblem = z.infer<typeof ApiProblemSchema>;
