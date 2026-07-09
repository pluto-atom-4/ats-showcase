## Title
Enhance Sub-Comment Review: Add Confirmation Dialog for Prior Review Status & Date

## Description

### Problem
When a user reviews a job that has been previously reviewed, the current implementation displays the prior review status and date inline (e.g., `[Prior: confirmed on 2026-07-01T14:22]`), but does not provide an easy way to quickly confirm or accept the prior decision without re-reviewing the entire job posting.

### Current Behavior
- Interactive review shows prior review info in job details
- User must make a new decision (confirm/reject/skip) even if prior decision is acceptable
- No fast-path option to accept prior review decision without re-evaluation

### Proposed Solution
Add a **sub-comment confirmation prompt** that:

1. **Displays prior review summary** in a dedicated section:
   ```
   Job: Senior Python Developer @ TechCorp
   ─────────────────────────────────────────

   📋 Prior Review:
      Status:   confirmed
      Date:     2026-07-01 14:22
      Tokens:   742 (estimated $0.002)

   ─────────────────────────────────────────
   ```

2. **Offers quick decision options**:
   - `[y]` - **Keep** (Accept prior decision without re-reviewing)
   - `[e]` - **Edit** (Change the prior decision)
   - `[r]` - **Re-review** (Full review of job content)
   - `[s]` - **Skip** (Review later)

3. **Tracks confirmation as lightweight audit**:
   - Record when user confirms prior review vs changes it
   - Store reason for changes (e.g., "confirmed prior decision")
   - Distinguish between "user re-reviewed and changed" vs "user accepted prior review"

### Benefits
- ✅ **Faster workflow** - Skip full review if prior decision is acceptable
- ✅ **Clearer intent** - Distinguish between user re-reviewing vs accepting
- ✅ **Better audit trail** - Know why decisions change
- ✅ **Cost reduction** - Fewer unnecessary LLM tokens for already-reviewed jobs

### Files to Modify
- `src/verification/reviewer.py`:
  - Add `_display_prior_review_summary()` method
  - Update `_process_user_action()` to handle new confirmation options
  - Add `_handle_confirm_prior_action()` for accepting prior review
  - Track confirmation in `review_audit` table with reason

### Implementation Steps

1. **Phase 1: UI Enhancement**
   - [ ] Create `_display_prior_review_summary()` to show prior status/date clearly
   - [ ] Update prompt to show new options when prior_review exists
   - [ ] Display 2-level confirmation: summary prompt → full review if needed

2. **Phase 2: Action Handler**
   - [ ] Implement `[y]` action to accept prior decision
   - [ ] Implement `[e]` action to edit prior decision
   - [ ] Update `_process_user_action()` to route to handlers
   - [ ] Save confirmation to review_audit with reason

3. **Phase 3: Audit Trail**
   - [ ] Add `confirmation_type` column to `review_audit` table ("re_review", "confirmed_prior", "edited_prior")
   - [ ] Track `confirmed_prior_at` timestamp when user accepts prior review
   - [ ] Add query method `get_confirmed_prior_reviews()` to show acceptance rate

4. **Phase 4: Testing**
   - [ ] Unit tests for new action handlers
   - [ ] Integration tests for user confirmations
   - [ ] Test audit trail recording
   - [ ] Verify backward compatibility

### Database Schema Changes
```sql
-- Add to review_audit table for tracking confirmation type
ALTER TABLE review_audit ADD COLUMN confirmation_type TEXT; -- 're_review', 'confirmed_prior', 'edited_prior'
ALTER TABLE review_audit ADD COLUMN confirmed_prior_at TIMESTAMP; -- When user accepted prior
```

### Success Criteria
- ✅ Users can quickly confirm prior review decisions without re-reviewing
- ✅ Confirmation is tracked separately from re-reviews in audit table
- ✅ Clear visual distinction between new reviews, re-reviews, and confirmations
- ✅ No breaking changes to existing review workflow
- ✅ All existing tests pass
- ✅ New tests cover confirmation paths

### Related Issues
- Issue #102 (Phase 3): Interactive Re-Review Workflow
- Issue #116: Assess Mode Filtering & Review Mode Options

### Notes
- This is an optional enhancement to Phase 3 of Issue #102
- Can be implemented independently or as part of Phase 3 improvements
- Focus on reducing re-review friction while maintaining data integrity
