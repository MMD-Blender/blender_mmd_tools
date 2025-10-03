# MMD Tools
MMD Tools is a Blender add-on for importing MMD (MikuMikuDance) model data (.pmd, .pmx), motion data (.vmd), and pose data (.vpd).
Exporting model data (.pmx), motion data (.vmd), and pose data (.vpd) are supported as well.

MMD ToolsはMMD(MikuMikuDance)のモデルデータ(.pmd, .pmx)、モーションデータ(.vmd)、ポーズデータ(.vpd)を
インポートするためのBlenderアドオンです。
モデルデータ(.pmx)、モーションデータ(.vmd)、ポーズデータ(.vpd)のエクスポートにも対応しています。

## Version Compatibility
| Blender Version | MMD Tools Version | Branch      |
|-----------------|-------------------|-------------|
| Blender 4.5 LTS | MMD Tools v4.x    | [main](https://github.com/MMD-Blender/blender_mmd_tools) |
| Blender 3.6 LTS | MMD Tools v2.x    | [blender-v3](https://github.com/MMD-Blender/blender_mmd_tools/tree/blender-v3) |

Use the MMD Tools version that matches your Blender LTS version.

## Installation & Usage
- Check the [MMD Tools Wiki](https://mmd-blender.fandom.com/wiki/MMD_Tools) for details.
- 詳細は [MMD ToolsのWiki (日本語)](https://mmd-blender.fandom.com/ja/wiki/MMD_Tools) を確認してください。

## Recommended Add-ons
While `mmd_tools` focuses on core import/export functionality, the community has developed excellent add-ons that provide advanced workflows.

-   **[MikuMikuRig](https://github.com/XiaoFFGe/MikuMikuRig):** A powerful, feature-rich add-on for advanced animation workflows. It provides a complete solution for using Blender's **Rigify** with MMD models, including one-click controller generation, retargeting, and baking the final animation back to a VMD-exportable format. This is the recommended solution for users who want to leverage Rigify for their MMD projects.

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
- Blender lacks collision mask functionality, requiring MMD Tools to use numerous rigid body constraints to simulate collision masks
- This constraint-heavy approach further degrades performance
- While MMD Tools provides `Assembly -> Physics` functionality, breast physics simulation doesn't closely match MMD behavior

**Recommended Workaround**:
For physics simulation, we recommend using [mmdbridge](https://github.com/rintrint/mmdbridge) and disabling Blender's rigid body physics entirely by clicking `Remove rigid body world` in Blender.

**Benefits of this approach**:
1. Significantly reduces Blender crashes
2. Physics effects match MMD exactly without having to manually recreate breast physics
3. Better overall performance

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

## License
Distributed under the [GPLv3](LICENSE).
