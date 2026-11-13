# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

require_relative "redmine_ai_helper_dmsf/settings"
require_relative "redmine_ai_helper_dmsf/patches/ai_helper_settings_helper_patch"
require_relative "redmine_ai_helper_dmsf/patches/ai_helper_settings_controller_patch"

module RedmineAiHelperDmsf
  # Adds this extension's tab to AI Helper's settings page and persists its
  # fields. Idempotent, so it can run from both to_prepare and after_initialize.
  #
  # The constants are referenced directly so Zeitwerk autoloads AI Helper's
  # helper and controller: require_dependency does not resolve files under a
  # plugin's app/ directory by name.
  # @return [void]
  def self.apply_patches
    helper = AiHelperSettingsHelper
    controller = AiHelperSettingsController

    unless helper < Patches::AiHelperSettingsHelperPatch
      helper.prepend Patches::AiHelperSettingsHelperPatch
    end
    return if controller < Patches::AiHelperSettingsControllerPatch

    controller.prepend Patches::AiHelperSettingsControllerPatch
  end
end
