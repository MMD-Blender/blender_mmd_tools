# MMD Tools

![Blender](https://img.shields.io/badge/Blender-4.2+-orange)
![License](https://img.shields.io/github/license/MMD-Blender/blender_mmd_tools)
![Release](https://img.shields.io/github/v/release/MMD-Blender/blender_mmd_tools)
![Downloads](https://img.shields.io/github/downloads/MMD-Blender/blender_mmd_tools/total)

MMD Tools is a Blender add-on for importing MMD (MikuMikuDance) model data (.pmd, .pmx), motion data (.vmd), and pose data (.vpd).
Exporting model data (.pmx), motion data (.vmd), and pose data (.vpd) are supported as well.

MMD ToolsはMMD(MikuMikuDance)のモデルデータ(.pmd, .pmx)、モーションデータ(.vmd)、ポーズデータ(.vpd)を
インポートするためのBlenderアドオンです。
モデルデータ(.pmx)、モーションデータ(.vmd)、ポーズデータ(.vpd)のエクスポートにも対応しています。

## Version Compatibility

Use the MMD Tools version that matches your Blender version.

| Blender Version | MMD Tools Version       | Branch                                                                         |
|-----------------|-------------------------|--------------------------------------------------------------------------------|
| Blender 4.2-5.2 | MMD Tools v4.x (latest) | [main](https://github.com/MMD-Blender/blender_mmd_tools)                       |
| Blender 3.6     | MMD Tools v2.x          | [blender-v3](https://github.com/MMD-Blender/blender_mmd_tools/tree/blender-v3) |

We recommend using Blender 4.2+ with the latest MMD Tools.
Support for Blender 3.6 is no longer maintained.

## Installation

### Blender 4.2+ (recommended)

1. Open Blender and ensure online access is enabled (`Edit → Preferences → System → Network → Allow Online Access`)
2. Go to `Edit → Preferences → Get Extensions`
3. Search for "MMD Tools"
4. Click `Install`

### Blender 3.6 (legacy)

1. Download [v2.10.3](https://github.com/MMD-Blender/blender_mmd_tools/releases/tag/v2.10.3)
2. In Blender: `Edit → Preferences → Add-ons → Install from Disk`
3. Select the downloaded `.zip` and enable "MMD Tools"

## Usage

- Check the [MMD Tools Wiki](https://mmd-blender.fandom.com/wiki/MMD_Tools) for details.
- 詳細は [MMD ToolsのWiki (日本語)](https://mmd-blender.fandom.com/ja/wiki/MMD_Tools) を確認してください。

## Recommended Add-ons

For advanced animation workflows using **Rigify**, we recommend the following community-developed add-ons:

Blenderの**Rigify**を使った高度なアニメーション制作には、以下のコミュニティ製アドオンを推奨します。

- **[MikuMikuRig](https://github.com/XiaoFFGel/MikuMikuRig)**
- **[MMD Tools Append](https://github.com/MMD-Blender/blender_mmd_tools_append)**

*Please note that these are third-party add-ons. For support and questions, please contact the respective authors.*

## Project Scope

The following features are intentionally excluded from MMD Tools:

- **PMX Editor replacement**: MMD Tools is not designed to replace PMX Editor functionality due to limited resources and to avoid reinventing the wheel
- **Blender Link features compatibility**: Link features have known issues that need to be resolved by Blender developers, so we do not guarantee compatibility
- **Rigify compatibility**: Due to the complexity and maintenance burden, direct support for Rigify is not part of the core add-on. For users seeking advanced animation workflows with Rigify, we recommend community-developed solutions like the ones mentioned in the "Recommended Add-ons" section above.
- **Material Library system**: Implementing a full-featured material library would be equivalent to building a separate add-on, which is outside the scope of this project. Instead, users can define their own custom default materials by editing the startup file. For example, the `MMDShaderDev` Node Group can be customized and saved in the Blender startup file (`File > Defaults > Save Startup File`), allowing it to be automatically applied to new MMD models without modifying the add-on itself.

## Known Issues

### Rigid Body Physics Limitations

**Issue**: Blender's rigid body system has stability and performance issues when working with MMD physics.

**Details**:

- Blender's rigid body system is prone to crashes and has worse performance compared to MMD
- Blender lacks collision mask functionality, requiring MMD Tools to use numerous rigid body constraints to simulate collision masks. This constraint-heavy approach further degrades performance
- MMD uses an older version of Bullet (2.75) with "soft" constraints, whereas Blender uses a newer version of Bullet with "hard" constraints. As a result, MMD Tools cannot reproduce PMX physics exactly as they behave in MMD. While MMD Tools provides `Assembly -> Physics` functionality, breast physics simulation doesn't closely match MMD behavior

**Recommended Workaround**:
For physics simulation, we recommend using [MMDBridge](https://github.com/rintrint/mmdbridge) and disabling Blender's Rigid Body World to avoid unnecessary rigid body simulations.

**Benefits of this approach**:

1. Significantly reduces Blender crashes
2. Physics effects match MMD exactly without having to manually recreate breast physics
3. Better overall performance
4. Resolves IK solver differences between Blender and MMD

### IK Solver Differences

**Issue**: When importing VMD motion data created in MMD, the resulting poses differ from the original.

**Details**:

- Blender uses its own IK solver implementation which produces different results compared to MMD's IK solver
- This causes noticeable differences in character poses, especially for legs, arms, and other IK-controlled bones
- Manual adjustment is required to fix the difference when working in Blender

**Recommended Workaround**:
Using [MMDBridge](https://github.com/rintrint/mmdbridge) ensures IK calculations are performed using MMD's native solver, providing consistent results with MMD.

## Contributing

MMD Tools needs contributions such as:

- Document writing / translation
- Video creation / translation
- Bug reports
- Feature requests
- Pull requests

If you are interested in supporting this project, please reach out via the following channels:

- [MMD Tools Issues](https://github.com/MMD-Blender/blender_mmd_tools/issues)
- [MMD & Blender Discord Server](https://discord.gg/zRgUkuaPWw)

For developers looking to contribute code or translations, please check the [Developer Guide](DEVELOPER_GUIDE.md) for project guidelines and detailed workflows.

## Contributors

See the [Contributors list](CONTRIBUTORS.md) for the full list of authors and maintainers.

Detailed contribution history: [GitHub Contributors](https://github.com/MMD-Blender/blender_mmd_tools/graphs/contributors).

## License

Distributed under the [GPLv3](LICENSE).
