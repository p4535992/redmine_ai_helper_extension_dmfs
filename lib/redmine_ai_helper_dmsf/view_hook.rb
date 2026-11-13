# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

module RedmineAiHelperDmsf
  # Renders the DMSF page action from the layout hook.
  #
  # DMSF has no view hook on its document or folder page, so the partial emits a
  # permission-gated script that inserts the action next to the page's own
  # actions. The hook fires on every page, so the partial must decide quickly and
  # render nothing outside DMSF.
  class ViewHook < Redmine::Hook::ViewListener
    render_on :view_layouts_base_body_bottom, partial: "redmine_ai_helper_dmsf/document_action"
  end
end
