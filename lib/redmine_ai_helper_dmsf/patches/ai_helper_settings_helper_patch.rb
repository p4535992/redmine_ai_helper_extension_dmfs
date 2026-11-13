# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

module RedmineAiHelperDmsf
  module Patches
    # Adds this extension's tab to AI Helper's global settings page.
    #
    # The tab is appended to AI Helper's own tab list, so the fields are part of
    # the same form and are submitted with AI Helper's settings. Nothing in AI
    # Helper's views, model or migrations is replaced or copied.
    module AiHelperSettingsHelperPatch
      # Name of the appended tab, also used to keep the patch idempotent.
      TAB_NAME = "dmsf"
      # Partial rendered for the tab; resolved from this plugin's app/views.
      TAB_PARTIAL = "redmine_ai_helper_dmsf/settings_tab"

      # @param form [ActionView::Helpers::FormBuilder] AI Helper's settings form
      # @return [Array<Hash>] AI Helper tabs followed by this extension's tab
      def ai_helper_settings_tabs(form)
        tabs = super
        return tabs unless tabs.is_a?(Array)
        return tabs if tabs.any? { |tab| tab.is_a?(Hash) && tab[:name] == TAB_NAME }

        tabs + [
          {
            name: TAB_NAME,
            partial: TAB_PARTIAL,
            label: :"redmine_ai_helper_dmsf.settings.tab_label",
            f: form
          }
        ]
      end
    end
  end
end
