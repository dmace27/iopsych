import { z } from "zod";
import { InternalUserRoleSchema } from "./contracts";

export const AccountSchema = z.strictObject({
  id: z.uuid(),
  email: z.string().min(1),
  name: z.string().min(1),
  role: InternalUserRoleSchema,
  is_active: z.boolean(),
  version: z.number().int().positive(),
});
export const AccountPageSchema = z
  .strictObject({
    items: z.array(AccountSchema).max(100),
    next_cursor: z.uuid().nullable(),
  })
  .refine(
    (page) =>
      new Set(page.items.map((item) => item.id)).size === page.items.length,
  );
export const AccountUpdateSchema = z
  .strictObject({
    expected_version: z.number().int().positive(),
    role: InternalUserRoleSchema.optional(),
    is_active: z.boolean().optional(),
  })
  .refine((input) => input.role !== undefined || input.is_active !== undefined);
export const AccountQuerySchema = z.strictObject({
  limit: z.number().int().min(1).max(100).default(25),
  after: z.uuid().optional(),
});
export type Account = z.infer<typeof AccountSchema>;
export type AccountPage = z.infer<typeof AccountPageSchema>;
export type AccountUpdate = z.infer<typeof AccountUpdateSchema>;
