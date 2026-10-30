package com.secondline.ledger;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import java.math.BigDecimal;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** OM-03 NFR-02 golden rule 3: no binary floating point anywhere in the ledger's production code. */
class OM_03_ArchitectureTest {
    static final JavaClasses LEDGER = new ClassFileImporter()
            .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
            .importPackages("com.secondline.ledger");
    static final Set<String> FLOATS = Set.of("float", "double", "java.lang.Float", "java.lang.Double");

    static final ArchCondition<JavaClass> NO_FLOAT_TYPES = new ArchCondition<>("not use float/double types") {
        @Override
        public void check(JavaClass c, ConditionEvents events) {
            c.getFields().stream().filter(f -> FLOATS.contains(f.getRawType().getName()))
                    .forEach(f -> events.add(SimpleConditionEvent.violated(f, f.getFullName() + " is " + f.getRawType().getName())));
            c.getCodeUnits().forEach(m -> {
                if (FLOATS.contains(m.getRawReturnType().getName())) {
                    events.add(SimpleConditionEvent.violated(m, m.getFullName() + " returns " + m.getRawReturnType().getName()));
                }
                m.getRawParameterTypes().stream().filter(p -> FLOATS.contains(p.getName()))
                        .forEach(p -> events.add(SimpleConditionEvent.violated(m, m.getFullName() + " takes " + p.getName())));
            });
        }
    };

    @Test
    void OM_03_no_float_or_double_in_domain() {
        classes().should(NO_FLOAT_TYPES).check(LEDGER);
        noClasses().should().callMethod(BigDecimal.class, "valueOf", double.class)
                .orShould().callConstructor(BigDecimal.class, double.class)
                .check(LEDGER);
    }
}
